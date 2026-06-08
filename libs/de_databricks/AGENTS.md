# de_databricks

Databricks workspace admin toolkit — IAM, Unity Catalog, housekeeping,
Tableau sync, workspace onboarding, and catalog migration.

**Location**: `libs/de_databricks/src/de_databricks/`
**Import path**: `from de_databricks.<module> import <function>`
**Notebook setup**: `sys.path.append("/Workspace/Repos/shared/mono-dev/libs/de_databricks/src")`

## Owner
@wei_hao_tan @jeffrey_siew

## Architecture

Two-layer layout:
- **`src/de_databricks/`** — Library code. All imports are package-qualified.
  Functions accept `session`/`spark`/`dbutils` explicitly. Testable.
- **`notebooks/`** — Thin notebook shims that run on Databricks clusters.
  Each imports from `de_databricks.*` and wires widget params to library calls.

## Folder structure

```
libs/de_databricks/
├── pyproject.toml
├── AGENTS.md
├── README.md
├── src/
│   └── de_databricks/
│       ├── __init__.py
│       ├── common/          <- Session factory + utils
│       ├── account/         <- Service principal management (REST + SDK)
│       ├── iam/             <- SCIM groups, users, permissions
│       ├── compute/         <- Shared cluster provisioning
│       ├── workflow/         <- Job creation and management
│       ├── unitycatalog/    <- UC permissions, catalog binding
│       ├── housekeep/       <- User lifecycle + asset cleanup
│       ├── tableau/         <- Tableau group sync
│       ├── setup/           <- Workspace onboarding
│       └── migrate/         <- Catalog replication + validation
├── notebooks/               <- Databricks notebook shims + configs
│   ├── housekeep/
│   ├── tableau/
│   ├── setup/
│   ├── migrate/notebook/
│   └── tests/              <- Integration tests (run on cluster)
└── tests/                  <- Local pytest (import checks)
```

## Module import lookup

| I need to... | Import |
|---|---|
| Create a Databricks session | `from de_databricks.common.session import create_databricks_session` |
| Create an account session | `from de_databricks.common.session import create_databricks_acct_session` |
| Create a workspace session | `from de_databricks.common.session import create_databricks_workspace_session` |
| Create an AccountClient (SDK) | `from de_databricks.common.session import create_databricks_acct_sdk` |
| Create a Tableau session | `from de_databricks.common.session import create_tableau_session` |
| Validate email | `from de_databricks.common.utils import is_valid_email` |
| Validate group name | `from de_databricks.common.utils import validate_group_name` |
| Send email (SES) | `from de_databricks.common.utils import send_email` |
| Create/get service principal (REST) | `from de_databricks.account.iam import create_or_get_service_principal` |
| Create/get service principal (SDK) | `from de_databricks.account.iam_sdk import create_or_get_service_principal` |
| SCIM group CRUD | `from de_databricks.iam.db_group import create_new_group, update_group_details_members, ...` |
| Get user details | `from de_databricks.iam.db_group import get_user_details` |
| Create shared cluster | `from de_databricks.compute.shared_compute import create_shared_cluster` |
| Create/update workflow job | `from de_databricks.workflow.job import create_or_update_job` |
| UC permissions | `from de_databricks.unitycatalog.db_unity_catalog import update_permissions` |
| UC grants | `from de_databricks.unitycatalog.db_unity_catalog_grants import update_permissions` |
| Assign catalog to workspace | `from de_databricks.unitycatalog.db_unity_catalog import assign_catalog_to_workspace` |
| Housekeep users | `from de_databricks.housekeep.user import deactivate_users, remind_users` |
| Housekeep catalogs | `from de_databricks.housekeep.asset import housekeep_catalog` |
| Sync Tableau groups | `from de_databricks.tableau.users_and_groups import sync_users_group` |
| Migrate catalog | `from de_databricks.migrate.db_catalog_migrate import create_and_replicate_catalog` |
| Validate migration | `from de_databricks.migrate.db_validate_migrate import validate_catalog_replication` |

## Rules

- Pass `session`/`spark`/`dbutils` explicitly — never rely on globals in library code.
- Never hardcode secrets — use `dbutils.secrets.get(scope, key)`.
- All table paths must be fully qualified: `catalog.schema.table`.
- Notebook code must be a thin shim — business logic lives in `src/`.

## Local dev

```bash
make test P=libs/de_databricks
make lint P=libs/de_databricks
```
