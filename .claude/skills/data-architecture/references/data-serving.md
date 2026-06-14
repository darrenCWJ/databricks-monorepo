# Data Serving Patterns

## Choosing the right serving layer

| Consumer type | Latency | Concurrency | Recommended pattern |
|---|---|---|---|
| Analyst / BI tool | Minutes | Low (<50 concurrent) | Gold Delta + SQL warehouse |
| ML feature store read | Seconds | Medium | Gold Delta + SQL warehouse or Delta Sharing |
| Operational dashboard | <1 second | Medium (<200 rps) | Lakebase sync |
| User-facing web application | <10 ms | High (1000+ rps) | Lakebase sync + connection pool |
| SaaS product sync (Salesforce, HubSpot) | Hourly | N/A | Reverse-ETL (Census / Hightouch) |
| Cross-org data sharing | Hours to days | N/A | Delta Sharing |

Don't over-engineer. Most internal analytics workloads are fine with a SQL warehouse. Only reach for Lakebase when you have a concrete sub-second SLA with a real application on the other end.

---

## Pattern 1: Gold Delta + SQL warehouse

The default. No extra infrastructure.

```python
# DAB job: build gold table
df_gold.write.format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "false") \
    .saveAsTable(f"{catalog}.gold.budget_variance")
```

BI tools (Tableau, Power BI, Metabase) connect via the SQL warehouse HTTP path or JDBC. Point them at the gold table directly. They don't need warehouse admin access — just SELECT on the schema.

**SQL warehouse sizing:**
- Serverless (default) — autoscales to zero; ideal for bursty BI usage.
- Classic — only if you need a fixed connection pool (legacy JDBC drivers) or predictable query latency with no cold start.
- Size: start at 2X-Small, scale up if P95 query time exceeds 30 seconds. Track `system.query.history` to identify slow queries before upsizing.

---

## Pattern 2: Lakebase sync (sub-second OLTP reads)

Lakebase is a managed PostgreSQL-compatible serving database that stays in sync with your Delta tables. Use it when an application needs primary-key lookups faster than a SQL warehouse can provide.

### Architecture (Pattern D — triggered sync)

```
DAB job builds gold Delta table
         │
         ▼
Sync task runs after gold build (task dependency in bundle.yml)
         │
         ▼
Lakebase serving table (PostgreSQL-compatible)
         │
         ▼
Application reads from Lakebase view (not raw table)
```

### bundle.yml sync task

```yaml
tasks:
  - task_key: build_gold
    notebook_task:
      notebook_path: ./notebooks/build_gold
  
  - task_key: sync_to_lakebase
    depends_on:
      - task_key: build_gold
    notebook_task:
      notebook_path: ./notebooks/sync_lakebase
    job_cluster_key: sync_cluster
```

### Schema setup

Put schema definitions in `projects/{name}/lakebase/`:

```
lakebase/
├── schema.sql          # CREATE TABLE statements
├── views.sql           # masked views (see PII section below)
└── migrations/         # versioned schema changes (Liquibase or Flyway)
    ├── V001__initial_schema.sql
    └── V002__add_segment_column.sql
```

Initial schema:

```sql
-- lakebase/schema.sql
CREATE SCHEMA IF NOT EXISTS serving;

CREATE TABLE serving.customer_360 (
    customer_id     BIGINT PRIMARY KEY,
    segment         TEXT NOT NULL,
    email           TEXT,           -- masked at view layer
    lifetime_value  NUMERIC(18,2),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ON serving.customer_360 (segment);  -- for common filter pattern
```

### PII compliance at the serving layer

Applications must read from a **masked view**, not the raw table. The view applies the same masking logic as the Unity Catalog column mask function, but in PostgreSQL.

```sql
-- lakebase/views.sql
CREATE VIEW serving.customer_360_masked AS
SELECT
    customer_id,
    segment,
    CASE
        WHEN current_user IN (SELECT username FROM serving.pii_readers)
        THEN email
        ELSE 'REDACTED'
    END AS email,
    lifetime_value,
    updated_at
FROM serving.customer_360;

-- Revoke direct table access from application role
REVOKE SELECT ON serving.customer_360 FROM app_readonly;
GRANT  SELECT ON serving.customer_360_masked TO app_readonly;
```

If the gold Delta table has a Unity Catalog column mask, mirror the masking logic here. The two should always agree — add a CI test that queries both and compares a sample.

### Row-level security (PostgreSQL RLS)

For tables with row-level filters in Unity Catalog, add equivalent RLS in Lakebase:

```sql
ALTER TABLE serving.budget_variance ENABLE ROW LEVEL SECURITY;

CREATE POLICY cost_centre_policy ON serving.budget_variance
  FOR SELECT
  USING (
    current_user IN (SELECT username FROM serving.finance_full_access)
    OR cost_centre IN (
      SELECT cost_centre FROM serving.user_cost_centre_map
      WHERE username = current_user
    )
  );
```

### Schema migrations

Use Flyway or Liquibase for versioned schema changes. Never alter Lakebase schema by hand.

```sql
-- migrations/V002__add_segment_column.sql
ALTER TABLE serving.customer_360
ADD COLUMN IF NOT EXISTS ltv_tier TEXT;

CREATE INDEX CONCURRENTLY ON serving.customer_360 (ltv_tier);
-- CONCURRENTLY avoids table lock; safe for production with live traffic
```

Run migrations as a DAB task before the sync task, not after:

```yaml
tasks:
  - task_key: run_migrations
    notebook_task: { notebook_path: ./notebooks/run_lakebase_migrations }
  - task_key: sync_to_lakebase
    depends_on: [{ task_key: run_migrations }]
```

### Networking

By default, Lakebase is accessible over the public internet with TLS + username/password. For production workloads in regulated environments, use PrivateLink:

```hcl
# In Terraform
resource "databricks_lakebase_instance" "main" {
  name        = "serving-${var.environment}"
  enable_private_link = true
  vpc_endpoint_ids    = [aws_vpc_endpoint.lakebase.id]
}
```

PrivateLink ensures traffic never leaves the AWS network. Required for any table containing PII or Restricted data.

---

## Pattern 3: Reverse-ETL

For syncing gold aggregations into SaaS tools (Salesforce, HubSpot, Marketo).

The Databricks-native option is a DAB job that:
1. Reads the gold table
2. Calls the SaaS API in batches
3. Tracks `updated_at > last_sync_watermark` for incremental sync

```python
# In src/{package}/salesforce_sync.py
def sync_accounts_to_salesforce(
    df: DataFrame,
    sf_client: Salesforce,
    batch_size: int = 200,
) -> SyncResult:
    """
    Upsert Salesforce Account records from a gold DataFrame.
    Uses Salesforce Bulk API v2 for throughput >10k records.
    """
    records = df.select("account_id", "segment", "ltv").toPandas()
    results = []
    for i in range(0, len(records), batch_size):
        batch = records.iloc[i:i+batch_size].to_dict("records")
        result = sf_client.Account.upsert_list(batch, "External_Id__c")
        results.extend(result)
    return SyncResult(total=len(records), errors=[r for r in results if r["success"] is False])
```

Prefer a managed reverse-ETL tool (Census, Hightouch, Fivetran HVR) over hand-rolled API calls when:
- You're syncing to >2 SaaS destinations
- Non-engineers need to manage the mapping
- You need field-level change detection (don't sync a record if nothing changed)

---

## Audit trail

Every access to gold tables and Lakebase must be logged. Databricks provides this automatically via `system.access.audit`.

```sql
-- Query recent accesses to a gold table
SELECT
    event_time,
    user_identity.email,
    action_name,
    request_params.table_full_name
FROM system.access.audit
WHERE action_name IN ('getTable', 'runCommand')
  AND request_params.table_full_name LIKE '%gold%'
  AND event_time > CURRENT_TIMESTAMP - INTERVAL 7 DAYS
ORDER BY event_time DESC;
```

For SOC2 and regulatory compliance, forward this to a WORM (Write Once Read Many) S3 bucket via a scheduled audit export job. Keep 12+ months of audit data.

For Lakebase, enable PostgreSQL audit logging:

```sql
-- In postgresql.conf (via Terraform databricks_setting)
log_connections = on
log_disconnections = on
log_statement = 'ddl'          -- log all DDL; 'all' for full audit (verbose)
log_min_duration_statement = 1000  -- log queries >1s
```
