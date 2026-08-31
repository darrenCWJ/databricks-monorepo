# Data Analyst — 5-day onboarding

> **Note:** The `dbt/` directory is planned but not yet scaffolded. dbt-specific
> instructions below will apply once the first dbt project is created.

You will build dbt models for your team's domain, classified for IM8 + PDPA.

## What you'll touch in this repo
- `dbt/<team>/models/staging/` — light cleanup of bronze sources
- `dbt/<team>/models/marts/` — your team's facts/dims
- `dbt/<team>/models/**/schema.yml` — column classification (REQUIRED)
- `dbt/platform-core/` — read-only; you reference via `{{ ref('platform-core', ...) }}`

## Day 1 — tools
- Install `uv`, `dbt-databricks`, `make`
- `cp dbt/profiles.example.yml ~/.dbt/profiles.yml` — fill in your dev creds
- `cd dbt/<team>/ && uv run dbt deps && uv run dbt parse` — should succeed

## Day 2 — get familiar
- Read root `AGENTS.md`, `dbt/AGENTS.md`, your team's `dbt/<team>/AGENTS.md`
- Run `make dbt-build PROJECT=<team>` — watch what builds
- Browse `dbt/<team>/models/marts/schema.yml`: every column has `meta.pii`,
  `meta.classification`, `meta.sensitivity`, `meta.retention_days`

## Day 3 — pair on adding a column
- Find a simple "add this column" ticket
- Open the MR. Pre-commit will block if `meta.*` is incomplete — that's by design
- Get review from data-governance for the classification call

## Day 4 — first independent model
- Build a new `stg_*` or `dim_*` model
- Include `not_null` test on the PK, `unique` if applicable
- Use `dbt-expectations` for column-value ranges where useful

## Day 5 — promote your own project
- Your model is merged to `main`, tagged by CI, and running in dev
- Open an MR bumping your project's `ref` in `release/staging/<project>.yml`
- After the bake, a second MR bumps `release/prod/<project>.yml`
- Only your project moves — you are never waiting on anyone else's work

## Rules to internalise
1. Every column needs `meta.pii`, `meta.classification`, `meta.sensitivity`,
   `meta.retention_days`. Pre-commit enforces this.
2. Cross-project references via `{{ ref('platform-core', 'fct_orders') }}`,
   never copy-paste SQL.
3. `access: public` only on models intentionally consumed by other dbt projects.
