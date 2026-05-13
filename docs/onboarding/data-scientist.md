# Data Scientist — 5-day onboarding

You will build ML pipelines that train, register, and serve models from
Databricks, with the same DAB + AGENTS.md discipline as a data engineer.

## What you'll touch in this repo
- `apps/<team>-ml-*/notebooks/` — exploratory + training notebooks (.py or .ipynb)
- `apps/<team>-ml-*/src/<team>_ml_*/` — wrapped, tested Python
- `apps/<team>-ml-*/resources/mlflow_experiments/` — MLflow experiment configs
- `apps/<team>-ml-*/bundle.yml` — job + serving endpoint config
- `libs/ml-features/` (if it exists yet) — shared feature engineering

## Day 1 — tools + Databricks Git integration
- Install `uv`, `just`, `databricks` CLI
- In Databricks UI: User Settings → Linked accounts → register your GitLab PAT
  (see `docs/runbooks/bootstrap-ci-and-audit.md` Part 2)
- Clone the repo into a Databricks Git Folder for in-browser notebook editing

## Day 2 — read the layout
- Read `apps/<team>-ml-*/AGENTS.md` for an existing ML app
- Open the notebook → notice it's THIN (widgets + import + call)
- Open `src/<team>_ml_*/training.py` → the actual logic lives here
- Find the unit test in `tests/`

## Day 3 — extend a notebook
- Pair on adding a new feature to an existing training notebook
- Move the feature-engineering function out of the notebook into `src/`
- Write a unit test for it

## Day 4 — first MLflow run from the bundle
- `just bundle-deploy apps/<that-app> -t dev`
- Trigger the training job: `just bundle-run apps/<that-app> training -t dev`
- Verify the experiment appears in MLflow with your run logged

## Day 5 — register and serve
- Register a model version from your training run
- Update `resources/mlflow_serving/` to reference your version
- `just bundle-deploy ... -t dev` → endpoint live
- Smoke-test the endpoint with a single request

## Rules to internalise
1. Notebooks are thin entry points. Logic that isn't unit-testable doesn't ship.
2. Every model registered in MLflow has a corresponding tagged commit in main.
3. Features that are reused across pipelines belong in `libs/ml-features/`,
   not copy-pasted between notebooks.
4. PII columns in training data follow the same classification rules as
   anywhere else (see `data-analyst.md`).
