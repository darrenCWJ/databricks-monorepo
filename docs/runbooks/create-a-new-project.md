# Runbook: create a new project

Walks through creating a new project from zero — choosing the right kind,
scaffolding it, registering it everywhere, getting it through CI, and
deploying the first version. Plan for ~half a day end-to-end (excluding
business logic).

Use this when:
- You're starting a greenfield project (no legacy to migrate).
- You're not sure which function type or project style to use.

> This runbook is the human companion to the `creating-apps` skill
> (`.claude/skills/creating-apps/`), which drives the same flow interactively
> for AI agents. Keep the two in sync — the skill is the source of truth.

If you're migrating an existing legacy script, see
`docs/runbooks/migrate-a-script.md` instead.
If you're importing an existing Databricks Job, see
`docs/runbooks/import-existing-job.md`.

## Step 0 — decide the function type and style

Every project is one **Databricks Asset Bundle (DAB)** under
`projects/<domain>/`. Two choices define it.

**1. Function type** — what kind of work it does:

| Function | What it is |
|---|---|
| `pipeline` | batch ETL, ingestion, orchestration |
| `streaming` | real-time / continuous processing |
| `app` | web apps (Streamlit, Dash, Flask, React) |
| `dashboard` | BI dashboards / Lakeview |
| `api` | REST / HTTP service endpoints |
| `sync` | low-latency read (Lakebase sync) |
| `capture` | operational capture (CDC / events) |

**2. Project style** — how the code is laid out:

| Style | Default for | Layout |
|---|---|---|
| `notebook` | `pipeline`, `streaming`, `capture` | logic in `notebooks/`, no `src/` package, minimal `pyproject.toml` (lib deps only), **not** a uv workspace member |
| `src` | `app`, `api`, `dashboard`, `sync` | `notebooks/` are thin shims calling tested `src/<pkg>/` code, with `tests/` and `contracts/schema.yml` |

**Reusable code** shared by 2+ projects goes in a **library** under `libs/`
(not a project). Inline it in one project first; promote it to a lib only when a
second consumer appears.

> There is **no dbt project type** in this monorepo. SQL transforms live inside a
> project's `src/`/`notebooks/` using the medallion libraries in `de_toolbox`
> (copper → bronze → silver → gold).

## Step 1 — choose a name and confirm the owner

Naming convention:

| Kind | Pattern | Example |
|---|---|---|
| Project (DAB) | `projects/<domain>/<function>-<subdomain>` | `projects/fraud/alert-daily` |
| Library | `libs/<team>_common` or `libs/common_<thing>` | `libs/finance_common` |

The `<domain>` is the team handle (lowercase). The full project name is
`<function>-<subdomain>`, with an optional wildcard suffix (`-daily`, `-v2`,
`-batch`) to disambiguate. The domain prefix routes CODEOWNERS, `affected.py`,
pre-commit boundary checks, and CI fan-out.

Before scaffolding, check for a name collision:
`ls projects/<domain>/ 2>/dev/null | grep <name>`.
Cross-team data reads are flagged during code review, not at scaffold time.

## Step 2 — scaffold

```bash
# Python project (the style is inferred from the function type)
make new-project DOMAIN=fraud FUNCTION=pipeline NAME=alert-daily KIND=python

# Scala project (e.g. streaming)
make new-project DOMAIN=fraud FUNCTION=streaming NAME=events-v2 KIND=scala

# Shared library
make new-lib NAME=finance-common
```

The scaffold chooses the **style** from the function type (`notebook` for
`pipeline`/`streaming`/`capture`, `src` for `app`/`api`/`dashboard`/`sync`) and
writes the matching stub files. Fill every stub before committing — no TODOs in
committed files.

## Step 3 — register everywhere

Three files at the root must know about the new project.

### 3a. `pyproject.toml` workspace members (only Python apps + libs)

```diff
[tool.uv.workspace]
members = [
    "projects/finance/customer360-etl",
+   "projects/fraud/alert-daily",
    ...
    "libs/common_spark",
+   "libs/finance_common",
    ...
]
```

Scala projects and **notebook-only** projects are NOT uv workspace members.
Scala lives under `sbt`; notebook-only projects declare their lib deps in a
minimal `pyproject.toml` only.

### 3b. `CODEOWNERS`

```diff
# Apps
/projects/finance-*/                        @wei_hao_tan @jeffrey_siew
```

If your team prefix is already in CODEOWNERS as a wildcard
(`/projects/finance-*/`), you don't need a new line. Just verify the wildcard
matches your new project's name.

For a brand-new team, add the team-wide rule first (see
`codeowners-maintenance.md`).

### 3c. `docs/data-architecture.md`

This file is **auto-generated** from every project's `AGENTS.md` — don't edit it
by hand. Regenerate and commit it in the same MR:

```bash
make data-map          # regenerate from AGENTS.md files
make check-data-map    # CI runs this; it fails if the file is stale
```

Then sync the uv workspace:

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

Use existing projects for reference:
- `projects/finance/customer360-etl/AGENTS.md` — Python DAB, medallion pipeline
- `projects/fraud/streaming/AGENTS.md` — Scala streaming
- `projects/cdo/pdpa-erasure/AGENTS.md` — cross-cutting service-principal job

Length budget: ≤ 80 lines.

## Step 5 — write tests first (or alongside)

For Python apps and libs:
- Pure transforms in `src/<package>/transforms.py` or similar
- Unit tests in `tests/` using `pytest`
- Use `testing_utils.spark_fixture` for Spark
- Run: `make test P=projects/<domain>/<name>` — should run green before any deploy

For Scala:
- Tests in `src/test/scala/`
- Use ScalaTest
- Run: `make sbt-test P=projects/<domain>/<name>`

For output tables (every project that writes Delta):
- Declare every output column in `contracts/schema.yml` with its `data_type`
  and a `meta` block:
  - `pii: true|false`
  - `classification: Official-Open | Official-Closed | Restricted`
  - `sensitivity: Sensitive-Normal | Sensitive-High | NA`
  - `retention_days: <integer>`
- Pre-commit blocks the MR if any output column is missing these. Breaking
  changes (drop / rename / type-change) are blocked when downstream consumers
  exist.

The first MR should not contain business logic and zero tests. If you find
yourself there, stop and write tests for the existing scaffold first.

## Step 6 — configure deployment

Edit `projects/<domain>/<name>/bundle.yml`:

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
make lint P=projects/<domain>/<name>             # ruff + mypy (+ scalafmt for Scala)
make test P=projects/<domain>/<name>             # pytest (or sbt-test for Scala)
make bundle-validate P=projects/<domain>/<name>  # databricks bundle validate
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
- `test-python` / `test-scala` jobs fire for your scope
- `bundle-validate` runs for your DAB
- `security` stage (pip-audit + trivy + ruff-S) runs always

Expected feedback time: 3-5 minutes for an affected-only run.

Approvers per CODEOWNERS:
- Your team's leads (always)
- `@wei_hao_tan @jeffrey_siew` + `@wei_hao_tan @jeffrey_siew` (if any column is
  classified `Restricted`)
- `@wei_hao_tan @jeffrey_siew` (if you touched `.gitlab-ci.yml` or anything in
  `infra/`)

## Step 9 — first deploy to dev

When the MR merges to `main`, the `deploy-dev` job runs automatically:

- `databricks bundle deploy -t dev`
- `tools/scripts/audit_log.py` records the deploy in the WORM S3 bucket

Watch the deploy log. Trigger the job manually first time:

```bash
make bundle-run P=projects/<domain>/<name> JOB=<task_key> T=dev
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

- [ ] Decided the function type + project style (or a library)
- [ ] Picked a `<function>-<subdomain>` name (optional `-wildcard` suffix)
- [ ] Confirmed owner with team lead
- [ ] `make new-project DOMAIN=<domain> FUNCTION=<function> NAME=<name> KIND=python|scala` OR `make new-lib NAME=<name>`
- [ ] Added to `pyproject.toml` workspace members (Python src-style + libs)
- [ ] Added to `CODEOWNERS` (or verified existing wildcard matches)
- [ ] Regenerated `docs/data-architecture.md` with `make data-map`
- [ ] Filled in `AGENTS.md` (≤80 lines)
- [ ] Wrote at least one meaningful unit test (src-style projects)
- [ ] Every output column declared in `contracts/schema.yml` with classification metadata
- [ ] `## Runtime Dependencies` filled in AGENTS.md if project calls/reads other projects
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
  members (src-style), regenerate `docs/data-architecture.md` with
  `make data-map`, run `make setup`.
- **Skipped classification metadata on output columns.** Pre-commit blocks
  the MR. Fix: declare every column in `contracts/schema.yml` with `pii`,
  `classification`, `sensitivity`, `retention_days`. If unsure,
  `@wei_hao_tan @jeffrey_siew` will advise.
- **No `run_as:` for staging/prod.** The MR may pass dev deploy and then
  fail at staging/prod because there's no service principal to run the
  job. Fix: add `run_as: { service_principal_name: ${var.staging_sp} }`
  to each environment's target overrides in `bundle.yml`.
- **Business logic in a `src`-style project's notebook.** For `src`-style
  projects (`app`/`api`/`dashboard`/`sync`), notebooks are thin shims — extract
  the logic into `src/<package>/` and unit-test it. (For `notebook`-style
  projects — `pipeline`/`streaming`/`capture` — logic in `notebooks/` is
  expected and first-class per ADR-0004; lint only suppresses Databricks-runtime
  false positives, while security, bug, and real type checks still apply.)
- **Cross-team import (Python).** Pre-commit hook
  `check_boundaries.py` blocks `from <other_team>_<app> import ...`.
  Fix: promote shared code to `libs/`, or read via Delta/Lakebase
  contract.
- **Forgot to regenerate `data-architecture.md`.** `make check-data-map`
  fails in CI when it's stale. Fix: run `make data-map` and commit the result
  in the same MR that adds the project.

## See also

- `.claude/skills/creating-apps/` — the interactive (agent) version of this runbook
- `migrate-a-script.md` — bringing legacy scripts in
- `import-existing-job.md` — bringing existing Databricks Jobs in
- `lakebase-sync-design.md` — adding a Lakebase sync
- `codeowners-maintenance.md` — when CODEOWNERS needs editing
- `release-process.md` — promoting to staging/prod
