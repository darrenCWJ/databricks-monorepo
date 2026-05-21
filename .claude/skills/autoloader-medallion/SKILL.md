---
name: autoloader-medallion
description: >
  Databricks Auto Loader with Medallion Architecture (Bronze/Silver/Gold).
  Covers ingestion via cloudFiles, schema evolution, rescue data, deduplication,
  type casting, data quality expectations, aggregations, SCD Type 2, and
  Liquid Clustering. Uses Spark Declarative Pipelines (SDP) syntax.
  TRIGGER when: user creates a new ingestion pipeline, mentions Auto Loader,
  medallion architecture, bronze/silver/gold layers, streaming tables,
  or asks to ingest raw files into Delta Lake.
  SKIP: user is querying existing tables only (no ingestion/transformation).
version: 1.0.0
tags: [databricks, autoloader, medallion, bronze, silver, gold, streaming, sdp]
---

# Auto Loader + Medallion Architecture

## Architecture Overview

```
External Files → [Auto Loader] → Bronze (raw) → Silver (clean) → Gold (aggregated)
     ↓                              ↓                ↓                ↓
  S3/ADLS/GCS              Append-only         Deduped          Materialized
  JSON/CSV/Parquet         + metadata           + typed          + aggregated
                           + rescue data        + validated      + served
```

## Layer Responsibilities

| Layer | Purpose | Table Type | Cluster By |
|-------|---------|-----------|------------|
| Bronze | Raw ingestion, append-only, metadata enrichment | Streaming Table | `event_type`, `ingestion_date` |
| Silver | Dedup, type cast, validate, filter | Streaming Table | `primary_key`, `business_date` |
| Gold | Aggregate, materialize, serve | Materialized View or Streaming Table | aggregation dimensions |

## When to Use Each Gold Type

- **Materialized View**: Full-table aggregations (daily totals, summaries) — batch refresh.
- **Streaming Table**: Windowed aggregations (5-min rollups, session windows) — incremental.

---

## Bronze Layer — Raw Ingestion

### SQL Pattern (Preferred)

```sql
CREATE OR REFRESH STREAMING TABLE bronze_orders
CLUSTER BY (order_date)
AS SELECT
  *,
  current_timestamp() AS _ingested_at,
  _metadata.file_path AS _source_file,
  CASE WHEN _rescued_data IS NOT NULL THEN TRUE ELSE FALSE END AS _has_errors
FROM STREAM read_files(
  '/Volumes/${catalog}/${schema}/raw/orders/',
  format => 'json',
  schemaHints => 'order_id STRING, amount STRING, order_date STRING'
);
```

### Python Pattern

```python
from pyspark import pipelines as dp
from pyspark.sql import functions as F

@dp.table(
    name="bronze_orders",
    cluster_by=["order_date"],
    table_properties={"delta.autoOptimize.optimizeWrite": "true"}
)
def bronze_orders():
    return (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.inferColumnTypes", "true")
        .option("rescuedDataColumn", "_rescued_data")
        .load("/Volumes/${catalog}/${schema}/raw/orders/")
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
        .withColumn("_has_errors", F.col("_rescued_data").isNotNull())
    )
```

### Bronze Rules

- ALWAYS add metadata: `_ingested_at`, `_source_file`, `_has_errors`.
- ALWAYS configure `rescuedDataColumn` for malformed record capture.
- NEVER transform data at Bronze — keep raw.
- Accept duplicates — dedup happens at Silver.
- Use `schemaHints` for known columns; let inference handle the rest.
- Cluster by `event_type` + `ingestion_date` (low cardinality).

### Quarantine Pattern

```sql
CREATE OR REFRESH STREAMING TABLE bronze_quarantine AS
SELECT * FROM STREAM bronze_orders WHERE _has_errors = TRUE;
```

---

## Silver Layer — Clean & Validate

### SQL Pattern

```sql
CREATE OR REFRESH STREAMING TABLE silver_orders (
  CONSTRAINT valid_order_id EXPECT (order_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT valid_amount EXPECT (amount > 0) ON VIOLATION DROP ROW,
  CONSTRAINT valid_date EXPECT (order_date IS NOT NULL)
)
CLUSTER BY (customer_id, order_date)
AS SELECT
  order_id,
  customer_id,
  product_id,
  CAST(amount AS DECIMAL(18,2)) AS amount,
  CAST(order_date AS DATE) AS order_date,
  CAST(order_timestamp AS TIMESTAMP) AS order_timestamp
FROM (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY _ingested_at DESC) AS _rn
  FROM STREAM bronze_orders
  WHERE _has_errors = FALSE
)
WHERE _rn = 1;
```

### Python Pattern

```python
from pyspark.sql.window import Window

@dp.table(name="silver_orders", cluster_by=["customer_id", "order_date"])
@dp.expect_or_drop("valid_order_id", "order_id IS NOT NULL")
@dp.expect_or_drop("valid_amount", "amount > 0")
@dp.expect("valid_date", "order_date IS NOT NULL")
def silver_orders():
    return (
        spark.readStream.table("bronze_orders")
        .filter(F.col("_has_errors") == False)
        .withColumn("_rn", F.row_number().over(
            Window.partitionBy("order_id").orderBy(F.desc("_ingested_at"))
        ))
        .filter(F.col("_rn") == 1)
        .select(
            F.col("order_id"),
            F.col("customer_id"),
            F.col("product_id"),
            F.col("amount").cast("DECIMAL(18,2)").alias("amount"),
            F.col("order_date").cast("DATE").alias("order_date"),
            F.col("order_timestamp").cast("TIMESTAMP").alias("order_timestamp"),
        )
    )
```

### Silver Rules

- ALWAYS deduplicate (ROW_NUMBER by business key, ordered by `_ingested_at DESC`).
- ALWAYS cast types explicitly — especially `DECIMAL(p,s)` for money (never FLOAT).
- ALWAYS add expectations for critical fields.
- Filter out `_has_errors = TRUE` rows (they go to quarantine).
- Cluster by `primary_key` + `business_date`.
- Use `ON VIOLATION DROP ROW` for non-nullable constraints.
- Use `ON VIOLATION FAIL UPDATE` for truly critical invariants.

### SCD Type 2 (Slowly-Changing Dimensions)

```sql
CREATE OR REFRESH STREAMING TABLE silver_customers;

CREATE FLOW customers_scd2 AS
AUTO CDC INTO silver_customers
FROM stream(bronze_customers_cdc)
KEYS (customer_id)
APPLY AS DELETE WHEN operation = "DELETE"
SEQUENCE BY event_timestamp
COLUMNS * EXCEPT (operation, _ingested_at, _source_file, _has_errors, _rescued_data)
STORED AS SCD TYPE 2;
```

- Query current state: `WHERE __END_AT IS NULL`
- Point-in-time: `WHERE __START_AT <= date AND (__END_AT > date OR __END_AT IS NULL)`

---

## Gold Layer — Aggregate & Serve

### Materialized View (Full-Table Aggregation)

```sql
CREATE OR REFRESH MATERIALIZED VIEW gold_daily_revenue
CLUSTER BY (order_date)
AS SELECT
  order_date,
  COUNT(*) AS order_count,
  SUM(amount) AS total_revenue,
  COUNT(DISTINCT customer_id) AS unique_customers,
  AVG(amount) AS avg_order_value
FROM silver_orders
GROUP BY order_date;
```

### Streaming Table (Windowed Aggregation)

```sql
CREATE OR REFRESH STREAMING TABLE gold_orders_hourly
CLUSTER BY (order_hour)
AS SELECT
  window(order_timestamp, '1 hour').start AS order_hour,
  COUNT(*) AS order_count,
  SUM(amount) AS total_revenue
FROM STREAM silver_orders
GROUP BY window(order_timestamp, '1 hour');
```

### Gold Rules

- Use Materialized View for batch aggregations (daily, monthly totals).
- Use Streaming Table for windowed aggregations (hourly, 5-min rollups).
- Preserve key dimensions (don't over-aggregate — keep region, category, etc.).
- Cluster by the columns users will filter on (dashboard dimensions).

---

## Critical Syntax Rules

| DO | DON'T |
|----|-------|
| `CREATE OR REFRESH STREAMING TABLE` | `CREATE OR REPLACE` |
| `FROM STREAM read_files(...)` | `FROM read_files(...)` (missing STREAM) |
| `CLUSTER BY (col1, col2)` | `PARTITION BY` + `ZORDER BY` |
| `_metadata.file_path` | `input_file_name()` |
| `from pyspark import pipelines as dp` | `import dlt` (legacy) |
| `@dp.table(...)` | `@dlt.table(...)` (legacy) |
| `STORED AS SCD TYPE 2` | `STORED AS SCD TYPE "2"` (integer, not string) |

## Checkpoint Rules

- One unique checkpoint per stream — never share.
- Use UC Volumes: `/Volumes/catalog/schema/checkpoints/stream_name`.
- Never use DBFS for checkpoints.
- Naming: `{catalog}/{schema}/checkpoints/{target_table_name}`.

## Trigger Selection

| SLA | Trigger | Cost |
|-----|---------|------|
| < 1 second | Real-Time Mode | $$$ |
| 1-60 seconds | `processingTime('N seconds')` | $$ |
| Minutes to hours | `availableNow=True` (scheduled via Jobs) | $ |

Rule of thumb: trigger interval = SLA / 3.

## File Format Selection

| Format | Use When |
|--------|----------|
| JSON | Semi-structured, schema evolves frequently |
| CSV | Legacy flat files, external team delivery |
| Parquet | Pre-structured, typed data from upstream systems |
| Avro | Schema registry integration, Kafka sources |

## Liquid Clustering Keys by Layer

- **Bronze**: `event_type` + `ingestion_date` — filter by type and incremental loads.
- **Silver**: `primary_key` + `business_date` — entity lookups and time-range queries.
- **Gold**: aggregation dimensions (e.g., `category`, `region`, `year_month`) — dashboard filters.
- Limit to 4 keys max. Most selective column first.
- Use `["AUTO"]` if unsure — Databricks chooses based on query patterns.

## Production Checklist

### Bronze
- [ ] Auto Loader with `rescuedDataColumn`
- [ ] Metadata columns: `_ingested_at`, `_source_file`, `_has_errors`
- [ ] Quarantine table for malformed records
- [ ] Clustered by `event_type` + `ingestion_date`
- [ ] `delta.autoOptimize.optimizeWrite: true`

### Silver
- [ ] Deduplication by business key
- [ ] Explicit type casting (DECIMAL for money)
- [ ] Data quality expectations defined
- [ ] Filter out `_has_errors` rows
- [ ] Clustered by `primary_key` + `business_date`
- [ ] SCD Type 2 for slowly-changing dimensions

### Gold
- [ ] Materialized View for full-table aggregations
- [ ] Streaming Table for windowed aggregations
- [ ] Key dimensions preserved (not over-aggregated)
- [ ] Clustered by dashboard filter columns
- [ ] Refresh schedule configured
