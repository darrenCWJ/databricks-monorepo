# Notebooks, src/, and the thin-shim pattern

Three folders look related but play different roles. Get them straight
once and refer back.

## `src/<package>/` — the application

All production code. Pure Python (or Scala), unit-testable,
ruff-checked, type-annotated. **All business logic lives here.**

For a pipeline:
```
src/<package>/
├── __init__.py     # public API
├── transforms.py   # pure transforms — unit-testable
├── io.py           # Spark reads / writes — integration-tested
├── schemas.py      # explicit StructTypes
└── _main.py        # orchestration only
```

For a Databricks App:
```
src/<package>/
├── __init__.py
├── app.py          # entry point (Streamlit / Dash / Flask)
├── data.py         # query helpers — unit-testable
├── components/     # reusable UI
└── pages/          # multi-page (Streamlit)
```

## `notebooks/` — thin shims, for pipelines only

Databricks Jobs execute notebooks. But notebooks can't be unit-tested
properly. So we use the **thin-shim pattern**: a 3-4 line notebook
file that does nothing except call into `src/`.

```python
# projects/finance-payment-recon/notebooks/run.py
# Databricks notebook source
from finance_payment_recon import _main
_main.run(spark=spark, dbutils=dbutils)
```

That's the **entire** notebook. No SQL, no filters, no transforms, no
`if` / `for` blocks. Pre-commit + reviewers block notebooks that grow
beyond a handful of lines.

**Databricks Apps do not have a `notebooks/` folder.** Apps run from
`src/<package>/app.py`, launched by `app.yaml`'s command. No notebook
involved.

## Why this strictness on notebooks

1. **Notebooks can't be unit-tested.** Their cell-by-cell model fights
   pytest.
2. **Notebooks make code review hard.** Reviewers can't diff cell
   outputs sensibly.
3. **Notebooks invite copy-paste.** A snippet that runs once becomes a
   snippet that ships.
4. **`src/` is what the rest of the world looks like.** New joiners
   from any Python background recognise `src/<package>/transforms.py`
   immediately.

## Exception: exploration notebooks

Live under `projects/<name>/notebooks/explore/`. Never run by jobs.
Reviewer only checks that they don't:

- Read or write production tables.
- Contain hardcoded secrets.
- Persist results outside the notebook.

Anything proven valuable in an exploration notebook moves into
`src/<package>/transforms.py` with tests before shipping.

## What pre-commit + reviewers will block

- More than ~20 lines in a notebook (excluding cell magic).
- Any of: `def `, `class `, `for ... :`, `if __name__`.
- SQL strings longer than 5 lines.
- `dbutils.secrets.get(...)` in a notebook (secrets go in `_main.py`).
- A `notebooks/` folder inside a Databricks App project (Pattern G).

## Databricks Git folder workflow

Engineers can edit notebooks via the Databricks UI in a Git folder.
When they push, pre-commit fires on the GitLab side. The same rules
apply. See `runbooks/databricks-git-folder-workflow.md`.
