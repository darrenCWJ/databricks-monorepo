# Data architecture — cross-project dependencies

The map of every pipeline in the platform: who owns it, what it produces,
and who consumes it. Maintained as projects are added.

When you add or rename a project, edit one row in each of the four tables
below. The `tools/scripts/check_ownership_sync.py` hook will surface drift.

> Owners: `@cdo/platform-team`. Every team's MR that adds an app/lib/dbt
> project must also update this doc (CI will warn).

---

## 1. Project catalogue

| # | Project | Folder | Type | Owner | Reads from | Writes to | Schedule |
|---|---|---|---|---|---|---|---|
| 1 | `pdpa-erasure` | `apps/pdpa-erasure/` | Python DAB | `@cdo/data-governance` | Every Restricted PII table | `cdo_${env}.audit.pdpa_erasures` | On-demand |
| 2 | `customer360-etl` | `apps/customer360-etl/` | Python DAB | `@cdo/customer-data` | `bronze.customer_events`, `bronze.crm_accounts` | `silver.customer_360`, `gold.customer_lifetime_value` | Daily 02:00 SGT |
| 3 | `customer-segmentation-ml` | `apps/customer-segmentation-ml/` | Python DAB + MLflow | `@cdo/customer-data` | `silver.customer_360`, `platform-core.fct_orders` | `gold.customer_segments`, MLflow registry | Weekly Mon 04:00 |
| 4 | `fraud-streaming` | `apps/fraud-streaming/` | Scala DAB (streaming) | `@cdo/fraud-eng` | Kafka `fraud_signals` topic | `silver.fraud_alerts` | Continuous |
| 5 | `finance-gl-etl` | `apps/finance-gl-etl/` | Python DAB + dbt task | `@cdo/finance-team` | Upstream GL API, `bronze.finance_gl_entries`, `dbt/finance` outputs | `bronze.finance_gl_entries`, `silver.finance_budget_variance` | Daily 02:00 |
| 6 | `finance-payment-recon` | `apps/finance-payment-recon/` | Python DAB | `@cdo/finance-team` | `platform-core.fct_orders`, `bronze.finance_payments` | `silver.finance_payment_recon` | Daily 03:00 |
| 7 | `supplier-master` | `apps/supplier-master/` | Python DAB | `@cdo/supplier-team` | Supplier API, `bronze.supplier_submissions` | `bronze.supplier_master` | Daily 01:00 |
| 8 | `supplier-spend-analytics` | `apps/supplier-spend-analytics/` | Python DAB + dbt task | `@cdo/supplier-team` | `dbt/supplier` outputs, `platform-core.fct_orders` | `silver.supplier_spend_by_vendor` | Daily 04:00 |
| 9 | `supplier-risk-scoring` | `apps/supplier-risk-scoring/` | Python DAB + MLflow | `@cdo/supplier-team` | `silver.supplier_spend_by_vendor`, `bronze.supplier_master` | `gold.supplier_risk_scores`, MLflow registry | Weekly Sun 06:00 |
| 10 | `infra-asset-register` | `apps/infra-asset-register/` | Python DAB | `@cdo/infra-team` | CMDB API | `bronze.infra_assets` | Daily 00:30 |
| 11 | `infra-capacity-forecast` | `apps/infra-capacity-forecast/` | Python DAB + MLflow | `@cdo/infra-team` | `silver.infra_utilisation`, `dbt/infra` outputs | `gold.infra_capacity_forecast`, MLflow registry | Daily 05:00 |
| 12 | `platform-core` | `dbt/platform-core/` | dbt project | `@cdo/analytics-eng-platform` | All bronze sources | `fct_orders`, `fct_customers`, `dim_dates` (public marts) | Triggered by `apps/customer360-etl` daily |
| 13 | `finance` | `dbt/finance/` | dbt project | `@cdo/finance-team` | `bronze.finance_*`, `platform-core.fct_orders` | `fct_gl_entries`, `fct_budget_variance` (public) | Triggered as task in `apps/finance-gl-etl` |
| 14 | `supplier` | `dbt/supplier/` | dbt project | `@cdo/supplier-team` | `bronze.supplier_master`, `platform-core.fct_orders` | `fct_supplier_spend`, `dim_supplier` (public) | Triggered as task in `apps/supplier-spend-analytics` |
| 15 | `infra` | `dbt/infra/` | dbt project | `@cdo/infra-team` | `bronze.infra_assets`, `bronze.infra_metrics` | `fct_asset_utilisation`, `dim_asset` (public) | Triggered as task in `apps/infra-capacity-forecast` |
| 16 | `customer-data` | `dbt/customer-data/` | dbt project | `@cdo/analytics-eng-customer` | `silver.customer_360` | `fct_customer_engagement`, `dim_customer_attributes` (public) | Triggered as task in `apps/customer360-etl` |

---

## 2. Cross-project read matrix

Rows = consumers, columns = producers. ● means "reads from".

| Consumer ↓ \ Producer → | `platform-core` | `dbt/finance` | `dbt/supplier` | `dbt/infra` | `dbt/customer-data` | `customer360-etl` outputs |
|---|---|---|---|---|---|---|
| `apps/customer360-etl` | — | — | — | — | ● (own dbt) | — |
| `apps/customer-segmentation-ml` | ● `fct_orders` | — | — | — | ● `fct_customer_engagement` | ● `silver.customer_360` |
| `apps/finance-gl-etl` | ● `fct_orders` | ● (own dbt) | — | — | — | — |
| `apps/finance-payment-recon` | ● `fct_orders` | ● `fct_gl_entries` | — | — | — | — |
| `apps/finance-budget-variance` | — | ● `fct_gl_entries`, `fct_budget_variance` | ● `fct_supplier_spend` | — | — | — |
| `apps/supplier-master` | — | — | ● (own dbt) | — | — | — |
| `apps/supplier-spend-analytics` | ● `fct_orders` | — | ● `dim_supplier` | — | — | — |
| `apps/supplier-risk-scoring` | — | — | ● `fct_supplier_spend`, `dim_supplier` | — | — | — |
| `apps/infra-capacity-forecast` | ● `dim_dates` | — | — | ● `fct_asset_utilisation` | — | — |
| `dbt/finance` | ● `fct_orders`, `dim_dates` | — | — | — | — | — |
| `dbt/supplier` | ● `fct_orders`, `dim_dates` | — | — | — | — | — |
| `dbt/infra` | ● `dim_dates` | — | — | — | — | — |
| `dbt/customer-data` | ● `fct_orders` | — | — | — | — | ● `silver.customer_360` |

---

## 3. Pipeline composition patterns

| Logical pipeline | DAB | dbt project | Pattern | Tasks (in order) |
|---|---|---|---|---|
| Daily customer 360 | `apps/customer360-etl` | `dbt/customer-data` | **A** — DAB orchestrates dbt | `build_silver_customer360` → `dbt_build_customer_data` → `build_gold_clv` |
| Daily finance pipeline | `apps/finance-gl-etl` | `dbt/finance` | **A** — DAB orchestrates dbt | `ingest_to_bronze` → `dbt_build_finance` → `compute_variance` → `notify_if_anomalous` |
| Supplier spend & risk | `apps/supplier-spend-analytics` then `apps/supplier-risk-scoring` | `dbt/supplier` | **B** — Independent schedules | spend-analytics daily 04:00 with embedded dbt task; risk-scoring weekly Sun 06:00 reads spend output |
| Customer ML segmentation | `apps/customer-segmentation-ml` | (consumes `dbt/customer-data` only) | **B** — Independent schedule, no embedded dbt | `feature_engineering` → `train_model` → `score_population` |
| Infra capacity forecast | `apps/infra-capacity-forecast` | `dbt/infra` | **A** — DAB orchestrates dbt | `dbt_build_infra` → `train_forecast_model` → `publish_capacity_alerts` |
| Fraud streaming | `apps/fraud-streaming` | (none) | **C** — Pure app | `stream_fraud_signals` (Scala JAR, continuous) |
| PDPA erasure | `apps/pdpa-erasure` | (none) | **C** — Pure app | `erase` (on-demand, ticket-gated) |
| Platform spine | (none — invoked transitively) | `dbt/platform-core` | **C** — Pure dbt | Run by upstream DABs as part of their `dbt_task` |

Pattern legend:
- **A** — DAB defines `dbt_task` inline. One Job, one schedule. Best when Python + SQL share cadence.
- **B** — App and dbt have independent schedules. Tables are the contract.
- **C** — Pure app (streaming / ML / on-demand) or pure dbt (no Python involved).

---

## 4. Team dependency summary

| Team | Exposes (`access: public`) | Reads from other teams | Breaking changes affect... |
|---|---|---|---|
| `@cdo/analytics-eng-platform` | `fct_orders`, `fct_customers`, `dim_dates` | Bronze sources only | Every team. Mandatory deprecation; min 2-cycle notice. |
| `@cdo/customer-data` | `dim_customer_attributes`, `fct_customer_engagement`, `silver.customer_360` | `platform-core` | Finance budget variance, supplier spend analytics, ML segments |
| `@cdo/finance-team` | `fct_gl_entries`, `fct_budget_variance` | `platform-core`, `dbt/supplier` | Downstream dashboards, monthly close reports |
| `@cdo/supplier-team` | `fct_supplier_spend`, `dim_supplier` | `platform-core` | Finance budget variance; supplier risk-scoring |
| `@cdo/infra-team` | `fct_asset_utilisation`, `dim_asset` | `platform-core` (dates only) | Capacity-forecast ML; infra dashboards |
| `@cdo/fraud-eng` | `silver.fraud_alerts` | Kafka only (no UC reads) | Investigation tooling; fraud workflow |
| `@cdo/data-governance` | `audit.pdpa_erasures` | All Restricted tables | None outbound; inbound: data subjects |
| `@cdo/platform-team` | `libs/common-*`, infra, tools | None | Every team. Heaviest deprecation discipline. |

---

## How this doc stays accurate

- **At project creation:** the team adding the new app/lib/dbt project adds one row to Table 1 (catalogue) AND one row to Table 3 (composition).
- **When cross-project read is added:** the consuming team adds the ● mark to Table 2.
- **Quarterly:** `@cdo/platform-team` walks every row and verifies it still reflects reality (part of the standard quarterly access review).
- **CI:** the sync-checker will eventually validate that every project listed in `apps/`, `libs/`, `dbt/` appears in this doc. For now it's manual.

## See also

- `docs/runbooks/codeowners-maintenance.md` — when CODEOWNERS changes, cascade updates here.
- `docs/runbooks/migrate-a-script.md` and `docs/runbooks/import-existing-job.md` — both add new rows to this doc as their final step.
- `agent-friendly-monorepo-pitch.pptx` — slides 8 and 9 present this content visually.

---

## 5. Lakebase — operational layer alongside Delta

Lakebase is the managed-Postgres OLTP store native to Databricks. It sits
alongside the Lakehouse Delta tables under the same Unity Catalog
governance umbrella. Same classification contracts, same residency, same
audit trail — different optimisation target (row-level OLTP vs columnar
analytical).

### 5.1 Three sync patterns

| Pattern | Direction | Use when | Resource type in `bundle.yml` |
|---|---|---|---|
| **D — Delta -> Lakebase** | gold Delta -> Lakebase synced table | Analytical results must serve sub-10ms OLTP reads | `synced_database_tables` with `scheduling_policy: TRIGGERED` or `CONTINUOUS` |
| **E — Lakebase -> Delta** | Lakebase OLTP table -> Delta bronze | Capture operational writes into analytics without separate CDC | `synced_database_tables` with reverse spec |
| **F — Bidirectional** | Both directions, with conflict policy | Rare — ML score updates an OLTP row the app also writes | Explicit conflict policy required; document in `AGENTS.md` |

### 5.2 Sync catalogue (grows as projects adopt Lakebase)

| App | Source (Delta) | Target (Lakebase logical DB.table) | Pattern | Refresh |
|---|---|---|---|---|
| `apps/customer360-etl` | `${var.catalog}.silver.customer_360` | `customer_data.customer_360` | D | Triggered after silver build |
| `apps/finance-budget-variance` | `dbt/finance.fct_budget_variance` | `finance_ops.budget_variance` | D | Triggered nightly |
| `apps/customer-preferences` (planned) | (none — capture) | `customer_data.preferences` -> bronze | E | Continuous CDC |
| ... | ... | ... | ... | ... |

### 5.3 Compliance — what propagates through sync

| Concern | Lakebase behaviour |
|---|---|
| Column classification (PII, Restricted) | Unity Catalog tags propagate through sync. Restricted column stays Restricted. |
| Masking | Apply at Lakebase as a Postgres view over the synced table, gated by role membership. |
| PDPA right to erasure | `apps/pdpa-erasure/` deletes from Delta AND every Lakebase synced copy. See script. |
| Residency | Lakebase instance in `ap-southeast-1`. Cross-region sync blocked at network layer. |
| Audit | Lakebase audit log -> `cdo-soc2-audit-${env}` S3 bucket. |

### 5.4 Folder layout for Lakebase artefacts

```
infra/lakebase/         <-- Lakebase instance, network, roles. Owned by @cdo/platform-team.
apps/<team>-<name>/lakebase/    <-- per-app schemas, migrations, sync rule YAML
```

The platform team owns the instance; each app team owns its schemas and
its sync rules.

### 5.5 New role: backend / API engineer

Lakebase introduces a fourth role beyond data engineer / analyst /
scientist / business analyst: the **backend or API engineer** who reads
from and writes to Lakebase from external services. They don't
necessarily clone this monorepo, but the monorepo *owns* the schemas they
consume — they treat the Lakebase schema as a versioned contract.

