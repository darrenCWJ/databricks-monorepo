# Runbook: create a new project

Walks through creating a new project from zero — choosing the right kind,
scaffolding it, registering it everywhere, getting it through CI, and
deploying the first version. Plan for ~half a day end-to-end (excluding
business logic).

Use this when:
- You're starting a greenfield pipeline (no legacy to migrate).
- You're not sure whether what you're building is an app, a lib, a dbt
  project, or some combination.

If you're migrating an existing legacy script, see
`docs/runbooks/migrate-a-script.md` instead.
If you're importing an existing Databricks Job, see
`docs/runbooks/import-existing-job.md`.

## Step 0 — decide what kind of project this is

Three questions answer it:

| Question | Yes | No |
|---|---|---|
| Does this transform data that lives in Unity Catalog into a new table that other teams will read? | Add a **dbt project** (or extend an existing one) | Skip |
| Does this ingest data from outside UC, run ML, stream, or do anything non-SQL? | Add an **app** (DAB) under `apps/` | Skip |
| Is this code reused by 2+ apps? | Add a **library** under `libs/` | Inline it where used; promote to a lib later if needed |

Common combinations:

| What you're building | What you create |
|---|---|
| Daily batch pipeline that reads bronze, joins, writes silver/gold | App + dbt project for the SQL portion (Pattern A) |
| Streaming ingestion | App only (typically Scala). No dbt. |
| Pure SQL transforms over existing Delta tables | dbt project (or models added to an existing one) |
| ML training pipeline | App (Python + MLflow). Reads from dbt marts. |
| Cross-team library | Promote to `libs/` (rare — only when 2+ apps will use it) |
| App serving low-latency OLTP reads | App + Lakebase sync (Pattern D) — see `lakebase-sync-design.md` |

## Step 1 — choose a name and confirm the owner

Naming convention:

| Kind | Pattern | Example |
|---|---|---|
| App | `apps/<team>-<verb>-<noun>` | `apps/fraud-alert-daily` |
| Library | `libs/<team>-common` or `libs/common-<thing>` | `libs/finance-common` |
| dbt project | `dbt/<team>` | `dbt/finance` |

Prefix is the team handle (lowercase, hyphenated). The prefix routes
CODEOWNERS, `affected.py`, pre-commit boundary checks, and CI fan-out.

Before scaffolding, check for name collision: `ls apps/ | grep <name>`.
Cross-team data reads are flagged during code review, not at scaffold time.

## Step 2 — scaffold

For an app (Python):

```bash
make new-app NAME=fraud-alert-daily KIND=python
```

For an app (Scala):

```bash
make new-app NAME=fraud-streaming-v2 KIND=scala
```

For a library:

```bash
make new-lib NAME=finance-common
```

For a dbt project (manual — no scaffold yet):

```bash
mkdir -p dbt/finance/{models/staging,models/marts,macros,tests,seeds}
cp dbt/platform-core/dbt_project.yml dbt/finance/dbt_project.yml
# Edit name: from 'platform_core' to your project name
sed -i '' "s/platform_core/finance/g" dbt/finance/dbt_project.yml
touch dbt/finance/AGENTS.md
```

## Step 3 — register everywhere

Three files at the root must know about the new project.

### 3a. `pyproject.toml` workspace members (only Python apps + libs)

```diff
[tool.uv.workspace]
members = [
    "apps/customer360-etl",
+   "apps/fraud-alert-daily",
    ...
    "libs/common-spark",
+   "libs/finance-common",
    ...
]
```

Scala apps and dbt projects are NOT uv workspace members. They live
under their own toolchains (`sbt`, `dbt`).

### 3b. `CODEOWNERS`

```diff
# Apps
/apps/finance-*/                        @cdo/finance-team
```

If your team prefix is already in CODEOWNERS as a wildcard
(`/apps/finance-*/`), you don't need a new line. Just verify the wildcard
matches your new project's name.

For a brand-new team, add the team-wide rule first (see
`codeowners-maintenance.md`).

### 3c. `docs/data-architecture.md`

Add a row to Table 1 (Project catalogue) and a row to Table 3 (Pipeline
composition) showing what your project is, what it reads, what it writes.

If your project introduces new cross-project reads, add a ● to Table 2 in
the right row/column.

Then sync the workspace:

```bash
make setup
```

## Step 4 — fill in the AGENTS.md

The scaffolded `AGENTS.md` is a stub. Fill in:

- **What this bundle/lib/project does** (one paragraph)
- **Inputs** (specific tables / APIs)
- **Outputs** (specific tables / endpoints)
- **SLA** (if production)
- **Classification** of inputs/outputs (per IM8 vocabulary)
- **Owners** for code, schema changes, release management
- **Local dev commands**
- **Rules** specific to this project (e.g., "no floats for money")

Use existing apps for reference:
- `apps/customer360-etl/AGENTS.md` — Python DAB with dbt task
- `apps/fraud-streaming/AGENTS.md` — Scala streaming
- `apps/pdpa-erasure/AGENTS.md` — cross-cutting service-principal job

Length budget: ≤ 80 lines.

## Step 5 — write tests first (or alongside)

For Python apps and libs:
- Pure transforms in `src/<package>/transforms.py` or similar
- Unit tests in `tests/` using `pytest`
- Use `testing_utils.spark_fixture` for Spark
- Run: `make test P=apps/<name>` — should run green before any deploy

For Scala:
- Tests in `src/test/scala/`
- Use ScalaTest
- Run: `make sbt-test P=apps/<name>`

For dbt:
- Every model needs `not_null` on its PK
- `unique` on dim/fact PKs
- `meta.pii`, `meta.classification`, `meta.sensitivity`, `meta.retention_days`
  on EVERY column (pre-commit blocks the MR otherwise)
- Run: `make dbt-test PROJECT=<project>`

The first MR should not contain business logic and zero tests. If you find
yourself there, stop and write tests for the existing scaffold first.

## Step 6 — configure deployment (apps only)

Edit `apps/<name>/bundle.yml`:

- Set the job name and schedule (or `continuous: {}` for streaming)
- Define cluster (`job_clusters` block) using the platform-team-provided
  variables (`${var.cluster_node_type_id}`, etc.)
- Reference notebooks from `./notebooks/`
- Set `run_as: { service_principal_name: ${var.staging_sp} }` for non-dev
  targets (mandatory for SOC2 segregation of duties)
- Set email notifications on `on_failure`

If this project produces a public-facing output served via Lakebase, also
add a `synced_database_tables` resource — see
`docs/runbooks/lakebase-sync-design.md`.

## Step 7 — pre-flight check locally

```bash
make lint P=apps/<name>             # ruff + mypy + sqlfluff + scalafmt
make test P=apps/<name>             # pytest (or sbt-test for Scala)
make bundle-validate P=apps/<name>  # databricks bundle validate
```

All three must pass before opening an MR. If `bundle-validate` fails on a
reference to something that doesn't exist in dev yet (e.g., a Lakebase
instance), use `--variable` flags to override, or open a draft MR and
resolve in review.

## Step 8 — open the MR

The MR template (`/.gitlab/merge_request_templates/default.md`) asks for:

- A change ticket ID (mandatory for SOC2)
- Risk + rollback notes
- Data-classification touchpoints
- CODEOWNER approval not by author

CI runs the affected-only path:
- `lint` job runs over your diff
- `compute-affected` builds the JSON manifest
- `test-python` / `test-scala` / `test-dbt` jobs fire for your scope
- `bundle-validate` runs for your DAB
- `security` stage (pip-audit + trivy + ruff-S) runs always

Expected feedback time: 3-5 minutes for an affected-only run.

Approvers per CODEOWNERS:
- Your team's leads (always)
- `@cdo/data-governance` + `@cdo/restricted-cleared` (if any column is
  classified `Restricted`)
- `@cdo/security` (if you touched `.gitlab-ci.yml` or anything in
  `infra/`)

## Step 9 — first deploy to dev

When the MR merges to `main`, the `deploy-dev` job runs automatically:

- `databricks bundle deploy -t dev`
- `tools/scripts/audit_log.py` records the deploy in the WORM S3 bucket

Watch the deploy log. Trigger the job manually first time:

```bash
make bundle-run P=apps/<name> JOB=<task_key> T=dev
```

If the job fails, fix and re-MR. The dev environment is the sandbox.

## Step 10 — ship to staging and prod

When you're ready (could be same day for low-risk projects, or after a
shadow-run for migrations):

1. Release manager cuts `release/YYYY-MM-DD` from `main`
2. Trigger `deploy-staging` manually in GitLab
3. Bake on staging for ≥24 hours; run smoke tests
4. Trigger `deploy-prod` manually (requires a different approver than the
   merger — SOC2 segregation of duties)

See `docs/runbooks/release-process.md` for the full release cadence.

## Step 11 — capture the migration record

Add an ADR if this is a significant new pipeline:

```bash
cp docs/adr/0001-monorepo-architecture.md docs/adr/00NN-<your-project>.md
# Edit it: what the pipeline does, what alternatives you considered,
# what residual risks it carries, who owns it.
```

ADRs are optional for routine new projects but required when the project:
- Introduces a new cross-team data flow
- Establishes a new pattern (e.g., the first Lakebase sync of its kind)
- Touches Restricted data
- Has a non-obvious architectural choice

## Checklist (the short version)

- [ ] Decided the project kind (app / lib / dbt / mixed)
- [ ] Picked a `<team>-<verb>-<noun>` name
- [ ] Confirmed owner with team lead
- [ ] `make new-app NAME=NAME KIND=python|scala` OR `make new-lib NAME=NAME` OR manual dbt scaffold
- [ ] Added to `pyproject.toml` workspace members (Python)
- [ ] Added to `CODEOWNERS` (or verified existing wildcard matches)
- [ ] Added row(s) to `docs/data-architecture.md` (Tables 1, 2, 3)
- [ ] Filled in `AGENTS.md` (≤80 lines)
- [ ] Wrote at least one unit test (for non-dbt)
- [ ] Every dbt column has `meta.*` fields (pre-commit will block otherwise)
- [ ] `make lint` / `make test` / `make bundle-validate` all pass locally
- [ ] Opened MR with change-ticket ID
- [ ] CI green
- [ ] CODEOWNER approved (not by author)
- [ ] Merged to `main`, deployed to dev automatically
- [ ] Smoke-tested the dev deployment
- [ ] Captured in ADR if significant

## Common mistakes

- **Scaffolded but didn't register.** The new project exists on disk but
  is invisible to CI and tooling. Fix: add to `pyproject.toml` workspace
  members, run `make setup`.
- **Skipped the `meta.*` block on dbt columns.** Pre-commit blocks the
  MR. Fix: classify every column. If unsure, `@cdo/data-governance` will
  advise.
- **No `run_as:` for staging/prod.** The MR may pass dev deploy and then
  fail at staging/prod because there's no service principal to run the
  job. Fix: add `run_as: { service_principal_name: ${var.staging_sp} }`
  to each environment's target overrides in `bundle.yml`.
- **Notebook has business logic.** Reviewers (and the AGENTS.md lint)
  will flag this. Fix: extract the logic into `src/<package>/` and unit
  test it. Notebook becomes a 4-line shim.
- **Cross-team import (Python).** Pre-commit hook
  `check_boundaries.py` blocks `from <other_team>_<app> import ...`.
  Fix: promote shared code to `libs/`, or read via Delta/Lakebase
  contract.
- **Forgot to update `data-architecture.md`.** Sync-checker doesn't
  enforce this yet, but quarterly review will catch it. Cleanest to add
  the row in the same MR that adds the project.

## See also

- `migrate-a-script.md` — bringing legacy scripts in
- `import-existing-job.md` — bringing existing Databricks Jobs in
- `lakebase-sync-design.md` — adding a Lakebase sync
- `codeowners-maintenance.md` — when CODEOWNERS needs editing
- `release-process.md` — promoting to staging/prod
