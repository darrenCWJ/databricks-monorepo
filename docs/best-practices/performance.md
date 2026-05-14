# Performance

## First rule

**Measure before optimising.** Use the Spark UI, not intuition. Job
timings live in the Databricks Job runs page; SQL plans live in the
SQL editor's "Query profile" tab.

## The five tunables that matter

1. **Partitioning.** See `data-modeling.md`. Right partitioning makes
   reads 10–100× faster.
2. **Liquid clustering** over manual partitioning for new tables. Lets
   Databricks rebalance automatically.
3. **`Z-ORDER BY` on filter / join columns** for legacy tables that
   can't move to liquid clustering yet.
4. **Photon-enabled clusters** for any SQL-heavy workload. ~2× faster
   at no extra cost — it's already in the platform defaults.
5. **AQE (Adaptive Query Execution)** is on by default. Leave it on.

## Joins — the most common cliff

- **Broadcast small sides.** If one side is < 100 MB, broadcast it:
  `spark.sql.autoBroadcastJoinThreshold` does this automatically up to
  its limit, but explicitly broadcasting via the `broadcast` hint is
  clearer in code.
- **Skew join on skewed keys.** Use the `skew` join hint when one key
  dominates the distribution.
- **Bucketing on the join key** is a legacy pattern — liquid clustering
  handles this better.

## Spark UI shortcuts

| Symptom | Likely cause | Where to look |
|---|---|---|
| One task takes 10× longer than others | Skew | Stages tab → task duration histogram |
| High shuffle reads | Wrong partition column or missing broadcast | Stages tab → shuffle read column |
| Lots of small files written | Coalesce / repartition before write | SQL tab → output rows / files |
| OOM on driver | Collecting too much data | Executor tab → driver memory |

## Cluster sizing

Start with the **platform default node type** (`${var.cluster_node_type_id}`).
Don't override unless you've measured. Most jobs are over-provisioned;
a few are under-provisioned. The Spark UI tells you which.

- **Autoscaling on for batch.** Min workers = 2, max = expected peak × 1.5.
- **Fixed size for streaming.** Autoscaling fights checkpointing.
- **Spot instances for non-prod.** ~70% cost savings; failed-task
  retries handle pre-emption.

## Costly things to avoid

- `df.collect()` on anything larger than a few MB. Use `df.show()` or
  write to a temp table.
- `df.cache()` without measuring — caching is not free.
- `repartition()` then immediately `coalesce()` — pick one.
- Reading the same Delta table 3 times in a job — read once, cache, reuse.
