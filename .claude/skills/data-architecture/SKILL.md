---
name: data-architecture
description: >
  Design and review data platform architectures on AWS + Databricks + Terraform. Use this
  skill when someone asks how to structure a lakehouse, design Unity Catalog namespaces,
  choose between batch and streaming ingestion, size Databricks compute, write Terraform
  for a data platform, decide how to serve data to downstream apps, or plan a migration
  from legacy pipelines to Delta Lake. Also invoke for questions about medallion layers,
  data access control patterns, multi-environment catalog design, or data-platform IaC.
  Trigger on phrases like "how do I design...", "should I use batch or streaming",
  "how to structure my catalogs", "what Terraform modules do I need", "how do I serve
  this data", "migrating to Databricks", or any architecture review touching Delta Lake,
  Unity Catalog, or Databricks Jobs.
compatibility:
  allowed-tools: Read, Grep, Glob, Bash(aws *), Bash(terraform *), Bash(databricks *)
---

# Data Architecture on AWS + Databricks

## Start here: five questions

Before recommending anything, understand the shape of the problem:

1. **Source type and volume** — Is data arriving as files, CDC events, API calls, or real-time streams? How much per day / hour?
2. **Read patterns** — Will consumers run batch analytics (SQL warehouse), train ML models (PySpark), or make sub-second OLTP lookups (application tier)?
3. **Compliance posture** — Does data contain PII? Are there row-level access restrictions, audit trail requirements, or data residency rules?
4. **Team and deployment model** — Is this a single team's pipeline or a shared platform serving many teams? Will multiple environments (dev/staging/prod) need isolation?
5. **Migration state** — Greenfield build? Migrating a legacy script or job? Introducing a parallel shadow copy first?

The answers determine which patterns below apply. Don't jump to implementation before you have them.

---

## Lakehouse topology

### Medallion layers

Organise every data store into three layers. Keep them as separate schemas, not separate tables within one schema — this makes access grants clean and cross-layer queries explicit.

| Layer | Purpose | Write pattern | Typical consumer |
|---|---|---|---|
| **Bronze** | Verbatim copy of the source, minimal transformation | Append-only, AUTOINCREMENT sequence or `_ingest_ts` | Audit, re-processing, lineage |
| **Silver** | Cleansed, typed, deduplicated, PII-tagged | Upsert (MERGE) or slowly-changing dimension | Data scientists, ML features |
| **Gold** | Business-ready aggregations, metrics, dimensional models | Overwrite or incremental MERGE | BI tools, dashboards, APIs |

Read `references/medallion-patterns.md` for detailed design patterns within each layer.

### Unity Catalog namespace design

Use the pattern `{env}_{domain}.{layer}.{table}`:

```
dev_fin.bronze.gl_transactions_raw
dev_fin.silver.gl_transactions
dev_fin.gold.budget_variance
```

Rules:
- **One catalog per domain per environment.** Isolation of grants, audit scope, and quota.
- **Three schemas per catalog:** `bronze`, `silver`, `gold`. Never create ad-hoc schemas.
- **Environment is a prefix, not a suffix** — `dev_fin`, not `fin_dev`. Makes catalog lists alphabetically grouped by environment.
- **Never hardcode a catalog name.** In DAB `bundle.yml` and PySpark code, reference `${var.catalog}` so targets switch environment automatically.

When to share vs isolate a catalog:
- Share if two teams both need SELECT on each other's silver tables as part of normal workflow.
- Isolate if the teams have different compliance tiers, release cadences, or budget owners.

---

## Batch vs streaming decision

| Scenario | Pattern | Tooling |
|---|---|---|
| Files land in S3 on a schedule (hourly / daily) | Auto Loader batch trigger → bronze Delta table | Databricks Auto Loader (`cloudFiles`), triggered DAB job |
| Files arrive continuously, sub-minute latency needed | Auto Loader continuous streaming → bronze | Structured Streaming DAB job, continuous cluster |
| CDC from a relational database | Debezium or Fivetran → bronze (Avro/JSON) → MERGE to silver | External CDC tool + silver MERGE job |
| Real-time event stream (Kafka/Kinesis) | Kafka source → Structured Streaming → silver upsert | Spark Structured Streaming, DeltaTable MERGE |
| Sub-10ms lookup by application | After gold is built: sync to Lakebase | Triggered sync job + Lakebase, see `references/data-serving.md` |

Default to **batch** until you have a concrete latency SLA under 5 minutes. Streaming clusters are always-on; the cost is 5–10× a job cluster for the same throughput.

---

## Compute sizing

### Job clusters (always prefer for production jobs)

Job clusters start fresh per run and terminate automatically. They are cheaper, more reproducible, and avoid noisy-neighbour interference.

| Workload | Recommended instance family | Notes |
|---|---|---|
| Standard PySpark ETL | `m7g` (Graviton3, arm64) | ~20% cheaper than x86 equivalents; Databricks Runtime 13.3 LTS+ supports arm64 |
| Memory-intensive joins / ML training | `r7g` (Graviton3 memory-optimised) | Use when spill occurs repeatedly |
| GPU model training | `g5` (A10G) | Only if training on the cluster; prefer SageMaker for long-running training |
| Scala streaming | `m7g.xlarge` min, autoscale to 8 workers | Match Kafka partition count to max workers |

Autoscaling rules:
- Set `min_workers: 1`, `max_workers` = peak parallelism estimate ÷ 8 (core count).
- Enable autoscaling only if job duration variance is >2×. Fixed clusters start faster.
- Always set `autotermination_minutes: 120` on all-purpose clusters.

### Serverless SQL warehouses

Use serverless SQL warehouses for BI tools and ad-hoc queries. They start in <5 seconds, scale to zero automatically, and cost nothing when idle. Classic warehouses make sense only when you need a fixed connection pool (e.g., legacy JDBC driver that doesn't handle reconnects).

---

## IaC structure

### Terraform module decomposition

Decompose Databricks + AWS infrastructure into five independent modules with a clear dependency chain:

```
iam ──────────────────────────────────────────────────────────┐
                                                               ▼
storage ◄── kms                    compute + catalog_grants ──►  workspace
                                                               ▲
unity_catalog ───────────────────────────────────────────────┘
```

1. **`modules/iam/`** — Groups, users, service principals, workspace role assignments. Runs against the MWS (account-level) API.
2. **`modules/storage/`** — S3 buckets (data, landing, autoloader, workspace), CMK encryption, Unity Catalog external locations.
3. **`modules/compute/`** — All-purpose dev cluster, instance pool, policy attachments. Workspace-level API.
4. **`modules/unity_catalog/`** — Catalog, bronze/silver/gold schema creation. Instantiate once per domain.
5. **`modules/grants/`** — `databricks_grants` resources. Separate from unity_catalog so grants can change without touching schema topology.

Apply order matters: `iam` → `storage` → `unity_catalog` → `grants` → `compute`.

For the full Terraform patterns, bucket naming, and CI/CD wiring see `references/terraform-databricks.md`.

### State backend

Always use S3 + native locking (no DynamoDB needed in recent Terraform):

```hcl
terraform {
  backend "s3" {
    bucket = "your-org-tfstate"
    key    = "databricks/${var.environment}/terraform.tfstate"
    region = "ap-southeast-1"
  }
}
```

One state file per environment per stack. Never share state between environments — blast radius control.

---

## Access control (four layers, all declarative)

Every access decision should live in a version-controlled Terraform file, not in the Databricks UI. The four layers from coarsest to finest:

| Layer | Gates | Where it lives |
|---|---|---|
| L1 Workspace | Who can log in; which SP a job runs as | SCIM sync from IdP + `run_as:` in `bundle.yml` |
| L2 Catalog/schema/table | USE_CATALOG, SELECT, MODIFY, CREATE | `databricks_grants` in Terraform |
| L3 Column masks | PII visibility (clear vs REDACTED) | dbt `schema.yml` `meta.mask_function` + Terraform function + dbt post-hook |
| L4 Row filters | Which rows a caller sees | dbt `schema.yml` `config.row_filter` + Terraform function + dbt post-hook |

Key rule: **humans get SELECT, service principals get MODIFY**. Never grant MODIFY to a human identity.

Every column that holds PII or Restricted data must declare a `mask_function`. Gating this in CI (pre-commit hook `check_pii_contract.py`) prevents the pattern from eroding under time pressure.

---

## Data serving patterns

| Consumer type | Latency need | Recommended pattern |
|---|---|---|
| BI tool / analyst | Minutes acceptable | Gold Delta table + SQL warehouse (JDBC/HTTP path) |
| ML training pipeline | Minutes acceptable | Silver/gold Delta table, read via PySpark or MLflow |
| Operational dashboard | <1 second | Lakebase sync from gold table |
| Web application (user-facing) | <10 ms | Lakebase sync + application reads Lakebase view (not raw table) |
| SaaS product (Salesforce, etc.) | Hourly acceptable | Reverse-ETL (Census, Hightouch) from gold tables |

Read `references/data-serving.md` for Lakebase setup, PII masking at the serving layer, and the schema migration pattern.

---

## Migration pattern

Use the **shadow write** approach for any migration from legacy to Databricks:

1. **Build the new pipeline** writing to `{table}_v2` (separate Delta table). Legacy continues writing to `{table}` unchanged.
2. **Run in parallel** for a validation window (minimum 7 days for daily jobs; 3 full load cycles for batch).
3. **Diff validate** — row counts, sums of numeric columns, sample record comparison. Automate this; do not eyeball it.
4. **Cut over** — point downstream consumers at `{table}_v2`. Rename after a grace period. Remove legacy job.
5. **Rollback path** — because `{table}` still exists and the legacy job is still running during the validation window, rollback is a config change, not an incident.

For migrating entire applications (scripts, notebooks, jobs) into a monorepo structure, use the `migrate-app` skill.

---

## Anti-patterns

These are the failure modes that compound over time. Call them out early.

- **Business logic in notebooks.** Notebooks cannot be unit-tested. Extract any function that transforms data into `src/{package}/` and test it with pytest. Notebook becomes a 4-line shim.
- **Hardcoded catalog names.** `cdo_prod.silver.customers` will break when you run the job in dev. Always use `${var.catalog}` in bundles and `spark.conf.get("catalog")` or a config object in code.
- **Manual grants via UI.** These don't appear in code review, don't get rolled back with Terraform, and vanish from the audit trail. Terraform only.
- **All-purpose clusters for production jobs.** They're shared, always-on, and expensive. Use job clusters.
- **Floats for money.** Floating-point rounding errors compound in financial aggregations. Use `DECIMAL(18,2)` in SQL, `Decimal` in Python, never `float` or `double`.
- **`SELECT *` in silver or gold.** Breaks schema evolution — adding a column upstream silently changes your downstream schema. Always select explicit columns.
- **Auto Loader without a rescue column.** Malformed records disappear silently. Always configure `cloudFiles.rescuedDataColumn` and land rescued data in a `_rescued_data` column you inspect.
- **One giant Terraform state file.** Separate state per environment, per stack. A misconfigured `terraform apply` on a monolithic state can affect prod.

---

## Related skills

- `autoloader-medallion` — detailed Auto Loader + DLT implementation with SDP conventions
- `databricks-lakebase` — Lakebase connection setup, querying, and data access patterns
- `creating-apps` — full lifecycle for a new DAB in this monorepo
- `aws-dev-toolkit:s3` — S3 bucket design, lifecycle policies, access control
- `aws-dev-toolkit:iam` — IAM roles, least-privilege policies, OIDC for CI
- `aws-dev-toolkit:networking` — VPC design, PrivateLink, security groups
- `aws-dev-toolkit:cost-optimizer` — rightsizing compute, Savings Plans, storage tiering
