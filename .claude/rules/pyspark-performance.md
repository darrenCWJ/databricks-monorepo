---
paths:
  - "**/*.py"
  - "**/*.ipynb"
  - "**/*.sql"
---
# PySpark Performance Rules

## DataFrame API

- Prefer built-in `pyspark.sql.functions` over UDFs — UDFs bypass Catalyst optimization.
- Always specify columns explicitly — never `SELECT *`.
- Filter early — apply predicates as close to source as possible.
- Use `F.col()` for lazy column references.

## Joins

- Broadcast small tables (<100MB): `spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "100m")`.
- For stream-to-static joins: use broadcast on the static side.
- For stream-to-stream joins: ALWAYS add watermark + time bounds to prevent state explosion.
- Include partition columns in join conditions for partition pruning.

## Partitioning & Clustering

- Use Liquid Clustering (preferred over Z-Order): `cluster_by=["col1", "col2"]`.
- Cluster by low-cardinality columns used in WHERE/JOIN clauses.
- Rule of thumb: < 100,000 total partition values.
- Bronze: cluster by `event_type` + `ingestion_date`.
- Silver: cluster by `primary_key` + `business_date`.
- Gold: cluster by aggregation dimensions.

## Delta Lake Operations

- Use `DeltaTable.merge()` for upserts — never DELETE + INSERT.
- Enable Deletion Vectors and Row-Level Concurrency for concurrent writes.
- Include partition columns in MERGE conditions for pruning.
- Target file size: 128MB (`delta.targetFileSize`).
- Cache DataFrames used in multiple MERGE operations, then `unpersist()`.

## Streaming

- ALWAYS set a trigger interval — prevents excessive cloud storage listing.
- Latency < 1s: Real-Time Mode. 1-60s: `processingTime`. Batch: `availableNow=True`.
- Never autoscale streaming clusters — use fixed-size for predictable latency.
- Set shuffle partitions equal to total worker cores.
- Target 100-200MB per partition in memory.
- One checkpoint per stream, never shared. Use UC volumes, not DBFS.

## Caching

- Cache intermediate results used multiple times: `df.cache()`.
- Always `unpersist()` when done.
- Never cache DataFrames that are only read once.

## SQL Best Practices

- NEVER use f-strings in SQL — use parameterized queries or named params.
- ALWAYS qualify table names: `catalog.schema.table`.
- Use materialized views for expensive aggregations read frequently.
- Run OPTIMIZE → VACUUM → ANALYZE in that order for maintenance.
