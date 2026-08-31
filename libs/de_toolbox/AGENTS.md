# de_toolbox

Shared Databricks pipeline library for medallion architecture, Data Vault,
Kimball, data quality, and external connectors.

**Location**: `libs/de_toolbox/src/de_toolbox/`
**Import path**: `from de_toolbox.<module> import <function>`
**Consumed as**: a wheel built by the consuming bundle (ADR-0006). Notebooks
just `import`; the project declares an `artifacts` entry and a task
`libraries: - whl:` in its `databricks.yml`. Never sys.path.append to a
workspace path.

## Owner
@wei_hao_tan @jeffrey_siew

## Architecture

Two module layers:
- **`de_toolbox.*`** — New code (V3). Explicit `spark` param. Testable. Use for new pipelines.
- **`de_toolbox._legacy.*`** — Old code (V1/V2). `global spark` pattern preserved. Use for backward compatibility with existing notebooks.

See `docs/adr/0002-de-toolbox-session-management.md` for rationale.

## Folder structure (for agents)

```
libs/de_toolbox/              <- Library root (not importable directly)
├── AGENTS.md                 <- You are here
├── pyproject.toml            <- Package metadata + deps
├── src/
│   └── de_toolbox/           <- The Python package (importable)
│       ├── __init__.py       <- Public API re-exports
│       ├── catalog.py        <- get_catalog, get_repo_path, get_tables
│       ├── validation.py     <- is_valid_email, is_valid_env, format_object_principal
│       ├── permissions.py    <- UC tags, ownership, grants
│       ├── delta.py          <- save_df_to_delta_with_column_mapping
│       ├── snapshot.py       <- create_monthly_snapshot
│       ├── notifications.py  <- send_email (SES)
│       ├── pipeline/         <- Medallion layers + modeling
│       │   ├── copper.py     <- V3 Auto Loader ingestion (JSON/CSV)
│       │   ├── bronze.py     <- V3 flatten + hash key
│       │   ├── silver.py     <- V3 transform + naming conventions
│       │   ├── gold.py       <- V3 monthly snapshot aggregation
│       │   ├── column_cleaning.py <- Column naming utilities (shared by copper/silver)
│       │   ├── data_vault.py <- Data Vault 2.0 hub/link/satellite
│       │   ├── kimball.py    <- Kimball V1 fact/dim/PIT
│       │   ├── kimball_v2.py <- Kimball V2 temporal views
│       │   ├── snapshot_bronze.py <- Bronze-to-mart snapshot
│       │   └── snapshot_silver.py <- Silver snapshot (Workday)
│       ├── connectors/       <- External system integrations
│       │   ├── auth.py       <- Workday JWT token (clean, no spark)
│       │   ├── sharepoint.py <- SharePoint Online connector
│       │   ├── workday.py    <- Workday connector
│       │   ├── workday_api.py <- Workday REST API client
│       │   └── wd_token.py   <- Workday token (alt implementation)
│       ├── quality/          <- Data quality + profiling
│       │   ├── profiling.py  <- Column-level statistics
│       │   ├── checks.py    <- DQ: completeness, conformity, validity, uniqueness
│       │   └── great_expectations.py <- GE-based DQ
│       ├── _legacy/          <- Old code (global spark, backward compat ONLY)
│       │   ├── autoloader_v1.py <- V1 create_bronze()
│       │   ├── autoloader_v2.py <- V2 create_bronze(), create_silver()
│       │   ├── copper_excel_csv.py <- Excel/CSV copper ingestion
│       │   ├── copper_landing_zone.py <- Landing zone copper
│       │   ├── data_vault_v1.py <- Data Vault (old interface)
│       │   ├── kimball_v1.py <- Kimball (old interface)
│       │   ├── sharepoint_v1.py <- SharePoint (old interface)
│       │   └── data_profiling_pipeline.py <- Profiling runner
│       └── _internal/        <- Implementation detail (do not import directly)
│           └── delta_impl.py <- Full save_df_to_delta_with_column_mapping logic
└── tests/                    <- Test suite (outside the package)
    ├── __init__.py
    ├── conftest.py
    ├── fixtures/
    └── test_*.py
```

## When to use what (V3 — new pipelines)

| I need to... | Import | Required args |
|---|---|---|
| Ingest JSON/CSV into copper | `from de_toolbox.pipeline.copper import create_copper_table` | `spark, dbutils, env, table_name, full_reload, config_dict` |
| Flatten + hash into bronze | `from de_toolbox.pipeline.bronze import create_bronze_table` | `spark, env, table_name, full_reload, config_dict` |
| Transform + clean into silver | `from de_toolbox.pipeline.silver import create_silver_table` | `spark, env, table_name, full_reload, config_dict` |
| Snapshot into gold | `from de_toolbox.pipeline.gold import create_gold_table` | `spark, env, table_name, full_reload, config_dict` |
| Data Vault 2.0 (hub/link/sat) | `from de_toolbox.pipeline.data_vault import create_silver` | `spark, project, metadata_name, env` |
| Kimball V1 (fact/dim/PIT) | `from de_toolbox.pipeline.kimball import create_gold` | `spark, project, metadata_name, env` |
| Kimball V2 (temporal views) | `from de_toolbox.pipeline.kimball_v2 import create_temporal_view` | `spark, ...` |
| Bronze snapshot | `from de_toolbox.pipeline.snapshot_bronze import process_bronze_to_mart_snapshot` | `spark, ...` |
| Silver snapshot | `from de_toolbox.pipeline.snapshot_silver import wd_snapshot` | `spark, ...` |
| Save DF with column mapping | `from de_toolbox.delta import save_df_to_delta_with_column_mapping` | `spark, df, table_path` |
| Monthly snapshot | `from de_toolbox.snapshot import create_monthly_snapshot` | `spark, df, primary_keys` |
| Get catalog name | `from de_toolbox.catalog import get_catalog` | `project, env` |
| Get tables in catalog | `from de_toolbox.catalog import get_tables` | `spark, catalog` |
| Set UC tags | `from de_toolbox.permissions import set_securable_object_tag` | `spark, meta_global, meta_local, object_full_path` |
| Change owner | `from de_toolbox.permissions import change_securable_object_owner` | `spark, meta_global, meta_local, project, env, object_full_path` |
| Grant permissions (dev) | `from de_toolbox.permissions import grant_securable_object_permission_in_dev` | `spark, meta_global, project, env, object_full_path` |
| Profile data | `from de_toolbox.quality.profiling import profile_data` | `df` |
| DQ checks | `from de_toolbox.quality.checks import dq_checks` | `spark, metadata, project, env` |
| Great Expectations DQ | `from de_toolbox.quality.great_expectations import main` | `spark, ...` |
| Send email (SES) | `from de_toolbox.notifications import send_email` | `sender, recipient, subject, body, get_secret=dbutils.secrets.get` |
| Workday JWT token | `from de_toolbox.connectors.auth import get_wd_token` | `client_id, user_id, private_key, api_url` |
| Workday API calls | `from de_toolbox.connectors.workday_api import workday_api` | `...` |
| Workday token (alt) | `from de_toolbox.connectors.wd_token import token` | `spark, dbutils, ...` |
| SharePoint Online | `from de_toolbox.connectors.sharepoint import main_SharePointOnline` | `spark, dbutils, ...` |

## Backward compatibility (_legacy)

For existing notebooks that use the old `from pipeline.X import *` pattern:

| Old import | New import (drop-in replacement) |
|---|---|
| `from pipeline.autoloader import *` | `from de_toolbox._legacy.autoloader_v1 import *` |
| `from pipeline.autoloader_v2 import *` | `from de_toolbox._legacy.autoloader_v2 import *` |
| `from pipeline.copper_excel_csv import *` | `from de_toolbox._legacy.copper_excel_csv import *` |
| `from pipeline.copper_landing_zone import *` | `from de_toolbox._legacy.copper_landing_zone import *` |
| `from pipeline.data_vault import *` | `from de_toolbox._legacy.data_vault_v1 import *` |
| `from pipeline.kimball_model import *` | `from de_toolbox._legacy.kimball_v1 import *` |
| `from pipeline.sharepoint import *` | `from de_toolbox._legacy.sharepoint_v1 import *` |

**_legacy modules preserve the `global spark` pattern.** They work identically
to the old code. Only the import path changed.

## Config format (V3 pipeline)

```yaml
domain: "your_domain"
subdomain: "your_subdomain"
copper:
  file_format: "json"|"csv"
  drop_columns: []
  ingest_timestamp_column: null
  ingest_date_format: null
  column_naming_convention: "pascal"
silver:
  column_naming_convention: "pascal"|"snake"|"camel"|"sanitized"
  rename_columns: {}
  transform: []
  drop_columns: []
gold:
  primary_keys: ["key1"]
  order_by_column: "_INGEST_DATE"
  snapshot_type: "period"|"current"
  report_date_adjustment: 0
```

## Config format (V1 pipeline — JSON metadata)

V1/V2 use JSON config files in `metadata/base/`. See the original README in
`de_toolbox/README.md` for full schema documentation (copper, bronze, silver layers).

Entry point: `create_bronze(spark, project, metadata_name, env, historical_load)`

## Rules

- **New code**: NEVER use `global spark`. Pass explicitly per ADR-0002.
- **New code**: NEVER import `from databricks.sdk.runtime import *`.
- **_legacy code**: `global spark` is acceptable (backward compat only).
- All table paths must be fully qualified: `catalog.schema.table`.
- Pure functions (validation, formatting) must NOT accept `spark`.
- For secrets in new code, pass `get_secret=dbutils.secrets.get` — not full `dbutils`.

## Local dev

```bash
make test P=libs/de_toolbox
make lint P=libs/de_toolbox
```

## Inputs
- Raw files in Databricks Volumes (`/Volumes/{catalog}/{schema}/raw_data/`)
- Unity Catalog tables (bronze, silver layers)
- JSON/YAML config files in `metadata/` directories
- SharePoint sites, Workday API endpoints

## Outputs
- Delta tables in Unity Catalog (copper, bronze, silver, gold layers)
- Data Vault tables (hub_, lnk_, sat_ prefixed)
- Kimball tables (fact_, dim_, pit_ prefixed)
- Data quality results in `databricks_dq_{env}` catalog
- Data profiling statistics tables
