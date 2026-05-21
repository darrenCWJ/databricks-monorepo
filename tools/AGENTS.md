# tools/ — Cross-cutting scripts

## What goes here
Utility scripts used across the monorepo for scaffolding, CI,
compliance, and developer productivity.

## Key scripts
| Script | Purpose |
|--------|---------|
| `scaffold.py` | Generate new apps/libs from templates |
| `affected.py` | Compute which bundles a PR impacts (for CI fan-out) |
| `audit_log.py` | Record deploys to the WORM audit bucket |
| `check_boundaries.py` | Block cross-team imports in Python |
| `check_pii_contract.py` | Ensure Restricted columns have mask declarations |
| `check_ownership_sync.py` | Verify CODEOWNERS matches folder structure |
| `lint_agents_md.py` | Validate AGENTS.md files follow conventions |
| `where_is.py` | Locate dbt models and their consumers |
| `dump_access.py` | Export access grants for quarterly audit |
| `diff_outputs.py` | Compare legacy vs new pipeline outputs during migration |
| `import_job.py` | Import an existing Databricks Job into a DAB |

## Rules
1. Scripts are owned by `@cdo/platform-team`.
2. Scripts must be invocable via `make` (see root `Makefile`).
3. No business logic here — only cross-cutting platform concerns.
