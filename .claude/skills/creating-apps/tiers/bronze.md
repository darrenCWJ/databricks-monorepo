# Bronze / Ingest Tier — Phase 3

## Step 3a: Ask about sources (all in one message)

```
Bronze tier — let's design the ingest layer.

1. How many sources does this app ingest?
   List each one briefly:
   e.g.  A) Payments API   B) Bank statement file drop

2. For each source, answer:
   a) Type:  REST API | CSV/Parquet file | Database (JDBC) | Kafka | Cross-app Delta read | Other
   b) Details:
      - API:  endpoint URL, HTTP method, auth type (API key / OAuth / bearer)
      - File: landing path (UC Volume: `/Volumes/<catalog>/<schema>/raw/<name>/`), format (json/csv/parquet)
      - DB:   connection alias, source table or query
      - Cross-app Delta read: which table from the list shown in Phase 0 Step 0c?
        (Delta reads need no ingest code — they go straight into Silver as inputs)
   c) Sample record: paste a row or list fields + types
      e.g.  payment_id: string, amount: float, currency: string, ts: timestamp
   d) Bronze table name:
      Recommended: `<catalog>.bronze.<source_name>`  — confirm or change
      (Cross-app Delta reads do not get a bronze table)
   e) Write mode:
      1. Append + partition by ingestion_date  (recommended)
      2. Full refresh (overwrite)

3. Task structure  (only if 2+ external sources)
   1. One combined ingest task  (simpler — sources run sequentially in one cluster)
   2. Separate task per source  (parallel execution, independent retry per source)
```

---

## Step 3b: Present Bronze design — wait for confirmation

```
BRONZE DESIGN
─────────────────────────────────────────────────────────────────
Source A: <type> — <endpoint / path>
  Bronze table : <catalog>.bronze.<name_a>
  Write mode   : <append by ingestion_date | full-refresh>
  Checkpoint   : /Volumes/<catalog>/<schema>/checkpoints/<name_a>  (file/Kafka only)
  Source fields:
    <field>  <type>
    ...
  Added by ingest:
    ingestion_date  date    — run date
    _source_file    string  — file path (_metadata.file_path, file/Kafka only)
    _source         string  — source identifier (API/JDBC only)
    _has_errors     boolean — true if _rescued_data is not null (file only)
    _rescued_data   string  — malformed fields captured by Auto Loader (file only)

Source B: <type> — <endpoint / path>
  Bronze table : <catalog>.bronze.<name_b>
  ...  — OR —  (none — cross-app Delta read, no ingest needed)

Cross-app reads (no ingest code):
  <catalog.schema.table>  owned by <app> (@cdo/<team>)
  ...  — OR —  none

Task structure:
  <1 combined task "ingest">  — OR —  <separate tasks: "ingest_a", "ingest_b">
─────────────────────────────────────────────────────────────────
Confirm or correct before code is written.
```

---

## Step 3c: Write Bronze code (after confirmation only)

**File layout:**
- One combined task → `src/<pkg>/ingest.py` with one function per source; `run(catalog, run_date)` calls all
- Separate tasks → `src/<pkg>/ingest_<source>.py` per source, each with its own `run(...)`
- Notebooks are always thin shims — no logic
- Tests: one per source covering field mapping and metadata columns

---

### Implementation patterns by source type

#### REST API
```python
import datetime as dt, requests
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F

def ingest_<name>(catalog: str, run_date: dt.date) -> DataFrame:
    spark = SparkSession.getActiveSession()
    records = _fetch_from_api(run_date)          # list[dict]
    df = (
        spark.createDataFrame(records)
        .withColumn("ingestion_date", F.lit(str(run_date)))
        .withColumn("_source", F.lit("<source-name>"))
    )
    (df.write.format("delta").mode("append")
       .partitionBy("ingestion_date")
       .saveAsTable(f"{catalog}.bronze.<name>"))
    return df

def _fetch_from_api(run_date: dt.date) -> list[dict]:
    """Stub — replace with real API client."""
    raise NotImplementedError
```

#### File Drop — Auto Loader (default for all file sources)
Uses `cloudFiles` with `trigger(availableNow=True)` so it runs as a one-shot batch
inside a standard DAB job. Auto Loader tracks which files have been processed —
no manual dedup needed.

```python
import datetime as dt
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F

def ingest_<name>(catalog: str, run_date: dt.date) -> DataFrame:
    spark = SparkSession.getActiveSession()
    checkpoint = f"/Volumes/{catalog}/<schema>/checkpoints/<name>"

    (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "<json|csv|parquet>")
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.schemaHints", "<field> <type>, ...")   # known cols
        .option("rescuedDataColumn", "_rescued_data")
        .load("/Volumes/<catalog>/<schema>/raw/<name>/")
        .withColumn("ingestion_date", F.lit(str(run_date)))
        .withColumn("_source_file", F.col("_metadata.file_path"))
        .withColumn("_has_errors", F.col("_rescued_data").isNotNull())
        .writeStream
        .format("delta")
        .option("checkpointLocation", checkpoint)
        .outputMode("append")
        .trigger(availableNow=True)
        .toTable(f"{catalog}.bronze.<name>")
        .awaitTermination()
    )
    return spark.table(f"{catalog}.bronze.<name>")
```

> Checkpoint rule: one unique path per stream — `/Volumes/<catalog>/<schema>/checkpoints/<name>`.
> Never use DBFS. Never share a checkpoint between two streams.

#### Database (JDBC)
```python
def ingest_<name>(catalog: str, run_date: dt.date) -> DataFrame:
    spark = SparkSession.getActiveSession()
    df = (
        spark.read.format("jdbc")
        .option("url",      dbutils.secrets.get("<scope>", "<jdbc-url-key>"))
        .option("dbtable",  f"(SELECT * FROM <table> WHERE date_col = '{run_date}') t")
        .option("user",     dbutils.secrets.get("<scope>", "<user-key>"))
        .option("password", dbutils.secrets.get("<scope>", "<password-key>"))
        .load()
        .withColumn("ingestion_date", F.lit(str(run_date)))
        .withColumn("_source", F.lit("<db-name>"))
    )
    (df.write.format("delta").mode("append")
       .partitionBy("ingestion_date")
       .saveAsTable(f"{catalog}.bronze.<name>"))
    return df
```

#### Kafka
```python
from pyspark.sql.types import StructType   # define schema for value payload

def ingest_<name>(catalog: str, run_date: dt.date) -> DataFrame:
    spark = SparkSession.getActiveSession()
    payload_schema = StructType([...])     # fill in fields
    checkpoint = f"/Volumes/{catalog}/<schema>/checkpoints/<name>"

    (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", dbutils.secrets.get("<scope>", "kafka-bootstrap"))
        .option("subscribe", "<topic>")
        .option("startingOffsets", "latest")
        .load()
        .select(
            F.col("key").cast("string"),
            F.from_json(F.col("value").cast("string"), payload_schema).alias("data"),
            F.col("timestamp").alias("_kafka_ts"),
        )
        .select("key", "data.*", "_kafka_ts")
        .withColumn("ingestion_date", F.to_date("_kafka_ts"))
        .withColumn("_source", F.lit("<topic>"))
        .writeStream
        .format("delta")
        .option("checkpointLocation", checkpoint)
        .outputMode("append")
        .trigger(availableNow=True)
        .toTable(f"{catalog}.bronze.<name>")
        .awaitTermination()
    )
    return spark.table(f"{catalog}.bronze.<name>")
