# Runbook: import an existing Databricks Job into the monorepo

Use this when a team has a Databricks Job that was authored in the workspace UI
(or via the Jobs API / Terraform / dbx) and now needs to live inside the
monorepo as a Databricks Asset Bundle.

End-to-end time: 1–3 days for a medium job, including the 7-day shadow run.

## When to use this vs `migrate-a-script.md`

| Starting point | Use this runbook |
|---|---|
| Existing Databricks Job already running in a workspace | **import-existing-job.md** (this) |
| Legacy ETL script that doesn't yet run on Databricks | `docs/runbooks/migrate-a-script.md` |
| Greenfield pipeline | `make new-app NAME=NAME KIND=python` — no runbook needed |

## Prerequisites

- The job ID of the existing Databricks Job. Find it in the workspace URL: `/jobs/987654321/...` → ID is `987654321`.
- `databricks` CLI authenticated against the source workspace.
- Decided on the target app name and owning team. Naming: `apps/<team>-<verb>`.
- An entry in your migration tracker (`docs/migrations/INDEX.md`).

## Step 1 — Inspect the existing job

Before exporting, screenshot or note these things in the UI:

- Tasks: how many, what type (notebook / Python wheel / JAR / SQL / dbt), task dependencies.
- Cluster: shared job cluster or task-specific? Node type, num workers, spark version, init scripts?
- Schedule: cron expression, timezone, paused or active?
- Parameters: list of base parameters and their default values.
- Permissions: who has CAN_MANAGE / CAN_VIEW today?
- Notifications: email-on-failure, duration warnings.
- Run-as identity: a user or a service principal?

Capture this in a `docs/migrations/<job>-import-notes.md` file — it becomes audit evidence and a checklist for the diff step.

## Step 2 — Scaffold the target app

```bash
make new-app NAME=finance-payment-recon KIND=python
```

Add it to the workspace and CODEOWNERS:

```diff
# pyproject.toml
[tool.uv.workspace]
members = [
    ...
+   "apps/finance-payment-recon",
]
```

```diff
# CODEOWNERS
+/apps/finance-payment-recon/    @cdo/finance-team
```

```bash
make setup
```

## Step 3 — Export the job from Databricks

```bash
make import-job JOB_ID=987654321 T=apps/finance-payment-recon
```

Under the hood this runs `tools/scripts/import_job.py`, which:

1. Calls `databricks jobs get --job-id 987654321 > /tmp/raw-job.json`
2. Calls `databricks bundle generate job --existing-job-id 987654321 --config-dir apps/finance-payment-recon/resources/jobs/ --source-dir apps/finance-payment-recon/`
3. Pulls referenced notebooks from `/Workspace/...` paths into `apps/finance-payment-recon/notebooks/`.
4. Rewrites notebook paths in `bundle.yml` to local refs (`./notebooks/...`).
5. Parameterises hardcoded `catalog: cdo_dev` to `catalog: ${var.catalog}`.
6. Converts inline clusters to a single `job_clusters` block parameterised on `${var.cluster_node_type_id}` and `${var.cluster_num_workers}`.
7. Strips the existing `job_id`, `creator_user_name`, `created_time` fields (these are workspace-managed).
8. Adds a stub `run_as: { service_principal_name: ${var.staging_sp} }` block (commented out for dev, uncommented for staging/prod).
9. Emits a summary report at `apps/finance-payment-recon/IMPORT_REPORT.md` flagging everything that needs human review.

## Step 4 — Human cleanup

Open `apps/finance-payment-recon/IMPORT_REPORT.md`. Typical items it flags:

- **Hardcoded paths.** Job referenced `dbfs:/mnt/legacy-bucket/...`. Switch to a Unity Catalog volume path (`/Volumes/${var.catalog}/...`).
- **User-bound run-as.** Job ran as `analyst.jane@cdo.gov.sg`. Replace with a service principal scoped to this app.
- **Init scripts.** Job used cluster init scripts. Decide whether they should be promoted to `libraries:` PyPI/Maven deps (preferred) or kept as init scripts (committed to `apps/<name>/scripts/init/`).
- **Workspace-only notebooks.** Job referenced `/Workspace/Repos/team/some-notebook`. Either copy the notebook into `apps/<name>/notebooks/` or reference it via a Git Folder.
- **Permissions.** Original job granted CAN_VIEW to a specific user. Replace with group-based grants.
- **Schedule.** Original schedule was unpaused. The scaffold paused it in dev; confirm prod target unpauses.

Each flagged item should be either:
- (a) resolved in the same MR, or
- (b) tracked as a follow-up issue with a TODO comment in `bundle.yml`.

## Step 5 — Add tests for the logic

The imported job probably has zero unit tests today. Before the MR is mergeable:

- Identify the transform functions inside the notebook(s).
- Move them into `src/finance_payment_recon/` as plain Python.
- Write `tests/test_*.py` covering the happy path and one edge case minimum.
- The notebook becomes a thin shim: widget read + import + call.

This is the single biggest improvement an import brings — it converts an untestable workspace job into a tested package.

## Step 6 — Validate locally

```bash
make lint P=apps/finance-payment-recon
make test P=apps/finance-payment-recon
make bundle-validate P=apps/finance-payment-recon
```

All three must pass.

## Step 7 — Open MR

Open the MR against `main`. CI runs affected-only. CODEOWNERS will route to:

- The owning team (`@cdo/finance-team`)
- Data-governance + cleared-reviewer (if any column in `dbt/finance/**/schema.yml` is touched or new PII columns are introduced)

The MR template's "How tested" section should reference the IMPORT_REPORT.md and confirm each flagged item is resolved or tracked.

## Step 8 — Shadow run (strangler-fig)

In `bundle.yml`, point the output table to a shadow:

```diff
base_parameters:
- output_table: ${var.catalog}.silver.payment_recon
+ output_table: ${var.catalog}.silver.payment_recon_v2
```

The legacy Databricks Job continues writing to `silver.payment_recon`. The DAB-managed job writes to `silver.payment_recon_v2`.

```bash
make bundle-deploy P=apps/finance-payment-recon T=dev
make bundle-run P=apps/finance-payment-recon JOB=payment_recon_daily T=dev
```

## Step 9 — Diff daily for ≥ 7 days

```bash
make diff-outputs BUNDLE=apps/finance-payment-recon LEGACY=\
  cdo_dev.silver.payment_recon \
  cdo_dev.silver.payment_recon_v2 \
  --key payment_id
```

Track results in your migration notes. Every diff must have a written explanation. Blockers stop progress.

## Step 10 — Cut over

When diffs are zero or explained, in one PR:

1. Drop the `_v2` suffix from `bundle.yml`.
2. Update downstream consumers (dbt models, reverse-ETL, dashboards) to read from the new table.
3. Stop the legacy Databricks Job — in a *separate* PR that disables/deletes it.

Capture the migration as `docs/adr/00NN-import-payment-recon.md`:

- What it did
- What changed in the rewrite
- What diffs were observed and accepted
- Cut-over date
- Legacy job decommission date

## Rollback (any time before step 10)

The migration is reversible until cut-over: the legacy job is still running and still writing the canonical table. To roll back, simply destroy the new DAB-managed job:

```bash
make bundle-destroy P=apps/finance-payment-recon T=dev
```

After cut-over, rollback means flipping consumers back to the legacy table (which still has historical data) and reactivating the legacy job. Plan for this taking ~30 minutes.

## Common questions

**Q: The job uses a JAR. Will this work?**
Yes. `spark_jar_task` is fully supported. The JAR lives at `apps/<name>/target/scala-2.12/...assembly.jar` (Scala) and is built by `make sbt-assembly P=apps/<name>`.

**Q: The job runs every 15 minutes — is shadow-running 7 days expensive?**
Yes — shadow-running doubles compute cost for that pipeline. For high-frequency jobs, consider a 3-day shadow with stricter diff thresholds, or shadow only during business hours. Document the deviation in the import notes.

**Q: We have 60 jobs to import. Can we batch?**
Yes. Group imports into migration waves of 3–5 per 2-week cycle. The cap exists because each import needs human review at Step 4 and Step 9, which doesn't parallelise well.

**Q: A job uses a notebook that calls another notebook via `%run`?**
The dependency must be made explicit. Either inline the `%run` target into the calling notebook (if it's small), or convert it into a Python module under `src/` and import it normally. `%run` doesn't survive a clean DAB structure.

**Q: We use Databricks Workflows that orchestrate multiple jobs across teams.**
Cross-team workflows become a top-level DAB owned by `@cdo/platform-team`, with `run_job_task` tasks pointing at jobs in team-owned bundles. The pattern is documented in `docs/runbooks/cross-team-workflows.md` (TODO).
