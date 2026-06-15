# apps/ — agent rules

> Extends the root AGENTS.md. Read that first.

## Two kinds of project

Every folder under `apps/` is either a **pipeline** (A–F) or a
**Databricks App** (G). The kind determines the folder structure
and what an agent should look for.

| If you see… | It's a… |
|---|---|
| `notebooks/` folder + `bundle.yml` with `jobs:` | Pipeline |
| `app.yaml` + no `notebooks/` | Databricks App |
| Both `app.yaml` AND `bundle.yml` with `apps:` | Databricks App (the bundle declares it) |

## Before you touch any app folder

1. Read `apps/<name>/AGENTS.md` for project-specific rules.
2. Check `bundle.yml` for target environments and resource type
   (job vs app).
3. For Databricks Apps, check `app.yaml` for the run command + env vars.

## Adding files to an existing pipeline

- Production code → `src/<package>/`.
- Tests → `tests/` (mirror `src/`).
- Notebooks → `notebooks/` (thin shims only).
- Job config → `bundle.yml`.

## Adding files to an existing Databricks App

- Production code → `src/<package>/`.
- UI components → `src/<package>/components/`.
- Pages (Streamlit) → `src/<package>/pages/`.
- Static assets → `static/`.
- App config → `app.yaml`.
- Tests → `tests/`.
- **Do not add `notebooks/` to an App project.** Apps don't run from
  notebooks.

## Never do this in an app folder

- Import from another app: `from <other_app> import …` is blocked by
  pre-commit.
- Put credentials in the repo. Use Databricks secret scopes referenced
  from `bundle.yml` or `app.yaml`.
- Put business logic in a notebook.
- For Databricks Apps: do not access user data directly from `app.py` —
  go through `data.py` so it's testable.

## When in doubt

Run `just where-is <table>` to find which app writes a given table, and
check that app's `AGENTS.md`.
