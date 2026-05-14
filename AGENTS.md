# CDO Platform — root rulebook

> This file is read by every AI agent (Claude, Genie Code, Cursor, Copilot)
> and every new engineer. Keep it under 200 lines. Per-folder AGENTS.md
> files extend this — they do not replace it.

## Stack

- **Compute**: Databricks on AWS GCC (Singapore region).
- **Languages**: Python (PySpark, pandas, scikit-learn, MLflow), Scala (streaming).
- **Build**: uv (Python workspace), sbt (Scala), Databricks Asset Bundles.
- **CI**: GitLab CI.
- **Quality gates**: pre-commit + GitLab pipelines.
- **Auth**: Cleared groups in GitLab → SCIM to Databricks workspace groups.

## What lives where

| Folder | Purpose | Owner pattern |
|---|---|---|
| `apps/<team>-<verb>-<noun>/` | A data pipeline or service. | `@cdo/<team>-team` |
| `libs/<team>-common/` or `libs/common-<thing>/` | Shared code, 2+ apps importing. | `@cdo/<team>-team` |
| `infra/` | Terraform + workspace config. | `@cdo/platform-team` |
| `docs/` | Architecture + how-tos. | `@cdo/platform-team` |
| `tools/` | Repo-wide helper scripts. | `@cdo/platform-team` |

## Rules every project must follow

1. **One folder per project under `apps/`**. No nested apps.
2. **No cross-team Python imports**. Promote shared code to `libs/`, or read
   data via Delta / Lakebase contracts.
3. **Every column in a Delta write contract has classification metadata**:
   `pii`, `classification`, `sensitivity`, `retention_days`. Pre-commit blocks
   the MR otherwise.
4. **No business logic in notebooks**. Notebooks are 4-line shims; logic
   lives in `src/<package>/` and has unit tests.
5. **`run_as:` service principal on every non-dev DAB target**. SOC2.
6. **No floats for money**. Use `Decimal` or `DECIMAL(p,s)`.

## What an AI agent should do before touching code

1. Read this file.
2. Read the AGENTS.md inside the folder you're editing.
3. For data writes: check the target table's classification — refuse the
   task if asked to write `Restricted` data without `mask_function` declared.
4. Run `just lint && just test` locally before suggesting a commit.

## Compliance touchpoints

- **IM8 Tier 1** — see `docs/compliance/im8.md`.
- **PDPA** — right-to-erasure runs from `apps/pdpa-erasure/` (you'll create
  this when first needed; see `docs/runbooks/`).
- **SOC2** — every deploy is logged via `tools/scripts/audit_log.py` to a
  WORM S3 bucket. Different approver for staging vs prod.

## Tooling pointers

| Need | Run |
|---|---|
| Add an app | `just new-app <team>-<verb>-<noun>` |
| Add a library | `just new-lib <team>-common` |
| Find a model | `just where-is <table_name>` |
| Show what an MR touched | `just affected` |
