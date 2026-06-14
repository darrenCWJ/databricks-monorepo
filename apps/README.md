# apps/

Every data pipeline AND every Databricks App lives here. One folder
per project.

## Two kinds of project

| Kind | What | Patterns |
|---|---|---|
| **Pipeline** | Produces or moves data. Runs as a Databricks Job on a schedule or stream. | A — Batch, B — Streaming, C — ML training, D/E/F — Lakebase syncs |
| **Databricks App** | Consumes data and serves a UI to users. Runs on serverless compute. | G — Databricks App |

## Folder naming

| Project kind | Pattern | Example |
|---|---|---|
| Pipeline | `apps/<team>-<verb>-<noun>/` | `apps/finance-payment-recon/` |
| Streaming pipeline | `apps/<team>-streaming-<noun>/` | `apps/fraud-streaming-events/` |
| ML training pipeline | `apps/<team>-ml-<noun>/` | `apps/credit-ml-churn/` |
| Databricks App | `apps/<team>-<noun>-app/` | `apps/finance-budget-app/` |

## Folder structure — pipeline

| File / folder | Purpose |
|---|---|
| `AGENTS.md` | Project rulebook |
| `bundle.yml` | Databricks Asset Bundle config (job, cluster, schedule) |
| `pyproject.toml` | Python package config |
| `build.sbt` | Scala build (Scala apps only) |
| `src/<package>/` | Production code. **All business logic lives here.** |
| `tests/unit/` + `tests/integration/` | Tests mirroring `src/` |
| `notebooks/` | **Thin shims** — 3–4 line files that call into `src/`. Databricks Jobs run these. |

## Folder structure — Databricks App

| File / folder | Purpose |
|---|---|
| `AGENTS.md` | Project rulebook |
| `app.yaml` | **Databricks Apps config** — command, env vars, resource refs |
| `bundle.yml` | DAB resource declaring the app |
| `pyproject.toml` | Python package config |
| `requirements.txt` | Frozen runtime deps for the app's serverless container |
| `src/<package>/app.py` | App entry point (Streamlit / Dash / Gradio / Flask / FastAPI) |
| `src/<package>/data.py` | Query helpers (SQL warehouse access) |
| `src/<package>/components/` | Reusable UI components |
| `static/` | Images, CSS, fonts |
| `tests/unit/` | Test data + business logic in isolation |
| `tests/e2e/` | (Optional) Playwright/Selenium for UI flows |

No `notebooks/` folder for Databricks Apps — apps aren't notebook jobs.
See `docs/best-practices/notebooks.md`.

## What goes in `src/` (both kinds)

**All business logic.** Pure Python, unit-testable, ruff-checked,
type-annotated. For pipelines: transforms, IO helpers, schemas. For
apps: UI code, query helpers, components.

The pre-commit hook `lint_agents_md.py` enforces: if a notebook contains
more than ~20 lines of logic, the MR is blocked. Logic belongs in
`src/`.

## Adding a new project

```bash
just new-app <team>-<verb>-<noun> --kind python   # pipeline
just new-app <team>-<noun>-app --kind app          # Databricks App
just new-lib <team>-common                          # shared library
```

Then follow `docs/runbooks/create-a-new-project.md`. For Apps
specifically, see `docs/runbooks/databricks-apps.md`.

## What this folder is NOT for

- Shared libraries (those go in `libs/`)
- Infrastructure code (that goes in `infra/`)
- Documentation (that goes in `docs/`)
