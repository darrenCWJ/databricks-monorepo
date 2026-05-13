# Runbook: migrate a single legacy script into the monorepo

Use this when you have a legacy ETL/ML/streaming script that needs to live in
`apps/`. The whole flow should take 1–3 days for a medium script.

## Step 1 — scaffold
```bash
just new-app my-pipeline --kind python    # or --kind scala
```
This creates `apps/my-pipeline/` with `bundle.yml`, `src/`, `tests/`, `notebooks/`, and an `AGENTS.md` stub.

Add the new package to root `pyproject.toml`'s `[tool.uv.workspace]` members list, then:
```bash
uv sync --all-packages
```

## Step 2 — lift
Copy the legacy script into `apps/my-pipeline/src/my_pipeline/`.
Replace ad-hoc imports with `from common_spark.session import get_spark` etc.
Move any inline business logic out of the notebook into a function in `src/`.

## Step 3 — wrap
Create a thin notebook in `apps/my-pipeline/notebooks/run.py`:
```python
dbutils.widgets.text("catalog", "cdo_dev")
from my_pipeline.job import run
run(dbutils.widgets.get("catalog"))
```
Write a unit test in `apps/my-pipeline/tests/` that exercises the function with a small local Spark.

## Step 4 — shadow
Deploy to dev alongside legacy, writing to a separate table:
```bash
just bundle-deploy apps/my-pipeline -t dev
just bundle-run apps/my-pipeline my_pipeline_daily -t dev
```
Configure `bundle.yml` so the new job writes to e.g. `silver.customer_360_v2`
while legacy continues writing to `silver.customer_360`.

## Step 5 — diff
Run for at least 7 calendar days, then:
```bash
just diff-outputs apps/my-pipeline \
  cdo_dev.legacy.customer_360 \
  cdo_dev.silver.customer_360_v2 \
  --key customer_id
```
All checks must pass or be explained in a comment on the migration PR.

## Step 6 — cut over
- Flip downstream consumers (dbt models, dashboards, reverse-ETL) to the new table.
- Decommission legacy: deploy with the legacy job removed.
- Write the migration record into `docs/adr/00NN-migrate-<name>.md`.

## Rollback
At any point before Step 6, the migration is reversible: legacy is still writing.
After cut-over, rollback means flipping consumers back; data already written
to the new table is preserved for forensics.
