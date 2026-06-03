# Runbook: design a Lakebase sync

When to add a Lakebase sync, which pattern to pick, how to wire it,
how to keep it compliant, and how to retire it.

## When to add a sync (and when not to)

Add a sync when:

- An application needs sub-10ms row-level reads of analytical data
  (customer-facing portal, real-time scoring, operational dashboard with
  per-record lookups).
- An operational service writes data that analytics needs to see — and you
  don't already have a separate CDC pipeline.
- ML features served to a low-latency endpoint must come from the same
  source-of-truth as the training data.

Don't add a sync when:

- Analytical SQL over Delta would be fast enough. Lakebase is a serving
  layer, not a faster lakehouse.
- The same data already lives in another OLTP store under separate
  ownership. Adding a sync makes two stores that can diverge.
- The downstream consumer only needs batch reads. Use a direct Delta read.

## Picking the pattern

| Question | Answer = D | Answer = E | Answer = F |
|---|---|---|---|
| Where does the data originate? | Delta | Lakebase | Both |
| What's the read pattern at the destination? | OLTP | Analytical | OLTP + analytical |
| Is there a write-back from the destination? | No | No | Yes |
| Refresh policy? | Triggered after Delta build, or continuous | Continuous CDC | Both directions, with conflict policy |

Default to **D** unless you have a strong reason for E. Reach for F only
when there's no way to avoid the same row being written from both sides.

## Wiring it in `bundle.yml`

Pattern D example — publish `silver.customer_360` to Lakebase:

```yaml
resources:
  synced_database_tables:
    customer_360_serving:
      name: customer_360
      database_instance_name: ${var.lakebase_instance}
      logical_database_name: customer_data
      source_table_full_name: ${var.catalog}.silver.customer_360
      spec:
        scheduling_policy: TRIGGERED
        primary_key_columns: [customer_id]
      # Column tags propagate from UC. Apply masking at Lakebase as a
      # Postgres view in apps/<name>/lakebase/views.sql.

  jobs:
    customer360_daily:
      tasks:
        # ... ingest + build silver ...
        - task_key: sync_to_lakebase
          depends_on: [{ task_key: build_silver_customer360 }]
          pipeline_task:
            pipeline_id: ${resources.synced_database_tables.customer_360_serving.pipeline_id}
```

The exact resource-type name follows whatever Databricks formalises in the
DAB schema; the shape stays the same.

## Schemas and migrations

Per-app schemas live at `apps/<name>/lakebase/`:

```
apps/customer360-etl/lakebase/
├── schema.sql              # CREATE TABLE customer_data.customer_360 (...)
├── views.sql               # masked views over PII columns
├── migrations/             # Liquibase / sqitch / Flyway migration files
└── sync_rules.yml          # human-readable mirror of the bundle.yml sync (optional)
```

Migrations run as a job task ahead of the sync:

```yaml
tasks:
  - task_key: apply_schema_migrations
    notebook_task:
      notebook_path: ./notebooks/run_migrations.py
      base_parameters:
        database: customer_data
  - task_key: sync_to_lakebase
    depends_on: [{ task_key: apply_schema_migrations }]
    # ... pipeline_task ...
```

## Compliance — what to check before merging

- Every PII column in the source Delta table has a corresponding **masked
  view** in `apps/<name>/lakebase/views.sql`. The application service role
  reads the view, not the underlying synced table.
- The `apps/pdpa-erasure/` script knows about this sync. Either:
  (a) the synced table is in the erasure walk, or
  (b) the sync is configured to propagate deletes from Delta automatically
       (preferred — verify in the sync spec).
- Lakebase audit log forwarder configured (one-time, per environment).
- Network: Lakebase instance + sync run inside the GCC VPC. No public endpoint.

## Operating the sync

- Initial sync (full snapshot) typically runs at first deploy; subsequent
  syncs are incremental.
- Monitor sync lag in Databricks UI -> Lakebase -> Synced tables. Alert
  threshold: sync_lag > 5 minutes for triggered, > 30 seconds for
  continuous.
- Failure recovery: re-trigger the sync task. Idempotent. The audit log
  records re-syncs.

## Retiring a sync

When the consuming app no longer needs Lakebase:

1. Remove the consumers (rollout to point at Delta directly).
2. Drop the `synced_database_tables` resource from `bundle.yml`.
3. `databricks bundle deploy -t prod` removes the sync.
4. Drop the Lakebase tables in a follow-up MR (separate, so the deletion
   is auditable).

## Quick reference

| Operation | Where |
|---|---|
| Define a sync | `apps/<name>/bundle.yml` `synced_database_tables:` |
| Schema DDL | `apps/<name>/lakebase/schema.sql` |
| Masked views for PII | `apps/<name>/lakebase/views.sql` |
| Migrations | `apps/<name>/lakebase/migrations/` |
| Instance setup | `infra/lakebase/main.tf` |
| Monitor sync lag | Databricks UI -> Lakebase -> Synced tables |
| Audit trail | `cdo-soc2-audit-${env}` S3 bucket |
