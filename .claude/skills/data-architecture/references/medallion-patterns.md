# Medallion Layer Patterns

## Bronze layer

### Auto Loader ingestion (recommended for file sources)

Auto Loader uses `cloudFiles` to detect new files in S3 without listing. It maintains a checkpoint so restarts are incremental.

```python
df = (
    spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "json")           # or csv, parquet, avro, xml
    .option("cloudFiles.schemaLocation", f"{checkpoint_path}/schema")
    .option("cloudFiles.rescuedDataColumn", "_rescued_data")  # always set this
    .option("cloudFiles.inferColumnTypes", "true")
    .load(f"s3://{landing_bucket}/raw/{source}/")
)

df.writeStream
    .format("delta")
    .option("checkpointLocation", f"{checkpoint_path}/ingest")
    .option("mergeSchema", "true")               # allow schema evolution
    .trigger(availableNow=True)                  # batch trigger (not continuous)
    .toTable(f"{catalog}.bronze.{table_name}")
```

**Key options explained:**
- `rescuedDataColumn` — records that fail schema inference land here instead of being silently dropped. Check `_rescued_data IS NOT NULL` in your silver validation.
- `availableNow=True` — processes all available files and stops, so you can schedule it as a job. Use `once=True` for legacy compatibility. Never use a continuous trigger for a batch source.
- `mergeSchema=True` — new columns in the source appear in bronze automatically. Silver explicitly casts, so new columns don't break silver until you handle them.

### Bronze schema conventions

Always add these audit columns at write time, not from the source:

```python
from pyspark.sql import functions as F

df_bronze = df.withColumn("_ingest_ts", F.current_timestamp()) \
              .withColumn("_source_file", F.input_file_name()) \
              .withColumn("_batch_id", F.lit(batch_id))
```

Bronze is **append-only**. Never MERGE or UPDATE bronze. If you need to fix a bad record, re-ingest with a corrected source file and let silver deduplication handle it.

### Schema evolution in bronze

When a new column appears upstream:
1. `mergeSchema=True` on the write adds it to the Delta table automatically.
2. The new column appears as `NULL` in all prior rows (expected — bronze is raw).
3. Silver must explicitly handle the new column before promoting it.
4. Never add business logic to bronze to handle the new column — that belongs in silver.

---

## Silver layer

### Deduplication

Two approaches depending on whether your source guarantees uniqueness:

**Approach A — MERGE upsert (preferred when source has a natural key):**

```python
from delta.tables import DeltaTable

silver = DeltaTable.forName(spark, f"{catalog}.silver.{table_name}")
silver.alias("tgt").merge(
    source=df_staged.alias("src"),
    condition="tgt.id = src.id"
).whenMatchedUpdateAll(
    condition="src._ingest_ts > tgt._ingest_ts"   # only update if newer
).whenNotMatchedInsertAll().execute()
```

**Approach B — window deduplication (when no reliable key, or source sends duplicates within a batch):**

```python
from pyspark.sql import Window

w = Window.partitionBy("business_key").orderBy(F.desc("_ingest_ts"))
df_deduped = (
    df_bronze
    .withColumn("_row_num", F.row_number().over(w))
    .filter("_row_num = 1")
    .drop("_row_num")
)
```

Use Approach B as a pre-step before Approach A when batches can contain duplicates.

### Type casting in silver

Cast explicitly. Never rely on inferred types surviving schema evolution.

```python
from pyspark.sql.types import DecimalType, TimestampType, IntegerType

df_silver = df_bronze.select(
    F.col("id").cast(IntegerType()),
    F.col("transaction_date").cast(TimestampType()),
    F.col("amount").cast(DecimalType(18, 2)),    # money: always Decimal, never double
    F.col("_rescued_data"),                       # pass through — inspected in validation
    F.col("_ingest_ts"),
)
```

Log a warning (don't fail) when `cast()` produces nulls on a column that should be non-null. Fail the job when null rate exceeds a threshold (e.g., >1% of rows).

### SCD Type 2 in silver (for slowly-changing dimensions)

Track history when the current value isn't enough — e.g., a customer's address changes and you need to know what address was valid at order time.

```python
# On each run, identify changed records
df_changes = df_incoming.join(
    df_silver_current.select("id", "address", "valid_from"),
    on="id", how="left"
).filter(
    (df_silver_current["address"] != df_incoming["address"]) |
    df_silver_current["id"].isNull()
)

# Close the old record
silver.alias("tgt").merge(
    source=df_changes.alias("src"),
    condition="tgt.id = src.id AND tgt.valid_to IS NULL"
).whenMatchedUpdate(set={"valid_to": F.lit(today)}).execute()

# Insert the new record
df_new_rows = df_changes.withColumn("valid_from", F.lit(today)) \
                        .withColumn("valid_to", F.lit(None))
df_new_rows.write.format("delta").mode("append").saveAsTable(f"{catalog}.silver.{table_name}")
```

Always add `is_current: boolean` as a derived column in gold for convenience — don't force gold users to filter `valid_to IS NULL` themselves.

### Column classification metadata

Every column in every silver/gold table must carry these metadata fields in the schema. This is a governance requirement, not optional:

```yaml
# In dbt schema.yml (or equivalent table comment in Terraform)
columns:
  - name: customer_email
    data_type: string
    meta:
      pii: true
      classification: Restricted      # Official | Restricted
      sensitivity: Sensitive-High     # Non-Sensitive | Sensitive-Normal | Sensitive-High
      retention_days: 2555            # 7 years
      mask_function: security.mask_pii  # required when classification = Restricted
```

In PySpark, attach as Delta column comments if not using dbt:

```python
spark.sql(f"""
  ALTER TABLE {catalog}.silver.customers
  ALTER COLUMN email COMMENT 'pii=true|classification=Restricted|sensitivity=Sensitive-High|retention_days=2555'
""")
```

---

## Gold layer

### Aggregation tables vs mart tables

- **Aggregation tables** — pre-computed metrics at a fixed grain (daily totals, weekly cohorts). Full overwrite each run. Fast to query, easy to reason about, but can't be queried at a different grain.
- **Mart tables** — dimensional model (fact + dims). Incremental MERGE. More flexible for ad-hoc analysis, but requires consumers to understand join logic.

Default to aggregation tables for BI dashboards (predictable queries). Use mart tables when the consumer needs to slice by arbitrary dimensions.

### Liquid Clustering vs Z-ORDER

Liquid Clustering (Delta 3.0+) replaces Z-ORDER for new tables:

```sql
CREATE TABLE catalog.gold.budget_variance
CLUSTER BY (cost_centre, period)    -- Liquid Clustering
AS SELECT ...
```

Use Liquid Clustering when:
- The table is written incrementally (MERGE/append) — Z-ORDER requires a full OPTIMIZE pass.
- You have 2–4 clustering columns.
- Table size >100 GB.

Keep Z-ORDER for tables you can't rewrite (existing large tables) or if you're on DBR <13.3.

### Partition pruning advice

Don't add `PARTITIONED BY` unless:
- The table is >1 TB, AND
- Most queries filter on the partition column with equality (not range).

Over-partitioning creates a small-files problem. `CLUSTER BY` achieves the same query speedup without the write amplification on small tables.

### OPTIMIZE and VACUUM schedule

```sql
OPTIMIZE catalog.gold.budget_variance;  -- compact small files, run weekly
VACUUM catalog.gold.budget_variance RETAIN 168 HOURS;  -- 7-day time travel window
```

Schedule OPTIMIZE as a separate DAB task, not inline with the main job. It holds a table lock and can block concurrent reads.
