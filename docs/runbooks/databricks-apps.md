# Runbook: building a Databricks App (Pattern G)

> For pipeline projects (Patterns A–F), see `create-a-new-project.md`.
> This runbook covers Databricks Apps specifically — user-facing web
> apps deployed on Databricks serverless compute.

## What's a Databricks App

A Python web app (Streamlit, Dash, Gradio, Flask, FastAPI) that runs
on Databricks-managed serverless compute. Use cases:

- Interactive dashboards backed by Lakebase or a SQL warehouse.
- Internal tools — data correction UIs, approval workflows, ops consoles.
- GenAI front-ends — RAG chat interfaces, model evaluation harnesses.
- Customer-facing apps (with appropriate IM8 + PDPA review).

See https://docs.databricks.com/dev-tools/databricks-apps/index.html for
the upstream docs.

## When to use Pattern G vs Pattern D

| Question | Pattern |
|---|---|
| "I need to serve fast reads to a UI my team builds elsewhere." | D — Lakebase publish |
| "I need to build the UI itself, and the UI lives inside Databricks." | G — Databricks App |
| "I need a customer-facing UI with custom branding outside Databricks." | (Not in this monorepo — separate web frontend that calls Lakebase / SQL warehouse.) |

Apps + Lakebase often pair: Pattern D publishes to Lakebase, Pattern G
reads from Lakebase and renders the UI. Two folders, two MRs, one
user-facing experience.

## Step 0 — pick a framework

| Framework | Best for | Why |
|---|---|---|
| **Streamlit** | Most internal data apps. | Fastest to build. Good defaults. |
| **Dash** | Heavy charting, interactive plots. | Plotly-native, more layout control. |
| **Gradio** | ML model demos, GenAI chat. | Built for ML workflows. |
| **Flask / FastAPI** | Anything HTTP-API-heavy. | Full control, more boilerplate. |

Default to Streamlit unless you have a specific reason to deviate.

## Step 1 — scaffold

```bash
just new-app finance-budget-app --kind app --framework streamlit
```

The scaffold produces:

```
apps/finance-budget-app/
├── AGENTS.md
├── app.yaml                  # Databricks Apps config
├── bundle.yml                # DAB resource declaring the app
├── pyproject.toml
├── requirements.txt          # frozen runtime deps
├── src/finance_budget_app/
│   ├── __init__.py
│   ├── app.py                # Streamlit entry point
│   ├── data.py               # query helpers
│   └── components/
├── static/
└── tests/
    └── unit/
```

No `notebooks/` folder. Apps don't run from notebooks.

## Step 2 — fill in `app.yaml`

`app.yaml` tells Databricks how to launch the app:

```yaml
command: ["streamlit", "run", "src/finance_budget_app/app.py",
          "--server.port", "8080"]
env:
  - name: DATABRICKS_WAREHOUSE_ID
    valueFrom: warehouse_id
  - name: APP_ENV
    value: "${var.env}"
```

The `valueFrom` references map to resources declared in `bundle.yml`.
The app inherits the workspace's networking, identity, and Unity
Catalog scoping automatically.

## Step 3 — write `src/<package>/app.py`

Minimal Streamlit example:

```python
# src/finance_budget_app/app.py
import streamlit as st
from finance_budget_app.data import fetch_budget_summary

st.set_page_config(page_title="Finance Budget", layout="wide")
st.title("Finance budget — Q1 2026")

# The logged-in user's identity is available via headers.
user = st.context.headers.get("X-Forwarded-Email", "unknown")
summary = fetch_budget_summary(user=user)
st.dataframe(summary)
```

Critical: **never `select * from <table>` in `app.py`.** Put queries in
`src/<package>/data.py` so they're testable in isolation.

## Step 4 — `bundle.yml` declares the app

```yaml
resources:
  apps:
    finance_budget_app:
      name: finance-budget-app
      source_code_path: .
      resources:
        - name: warehouse_id
          sql_warehouse:
            id: ${var.sql_warehouse_id}
            permission: CAN_USE
      # The app inherits run_as from this block:
      permissions:
        - level: CAN_USE
          group_name: cdo-finance-team
```

## Step 5 — auth + governance

- **User identity**: passed automatically. Read from
  `st.context.headers["X-Forwarded-Email"]` (Streamlit) or
  `request.headers.get("X-Forwarded-Email")` (Flask/FastAPI).
- **Data access**: the app runs as a service principal; that SP
  reads from Unity Catalog. Column masks + row filters apply per
  that SP's grants.
- **Per-user filtering**: if users should only see their own rows,
  pass the user identity to the query — don't trust client-side
  filters.

## Step 6 — test

Two layers:

1. **Unit tests** on everything in `src/<package>/data.py` and
   `src/<package>/components/`. Mock the SQL warehouse connection.
2. **E2E tests** (optional) with Playwright against a dev deployment.

```bash
just test apps/finance-budget-app
just bundle-validate apps/finance-budget-app
```

## Step 7 — deploy

Same flow as pipelines:

- Merge to `main` → auto-deploys to dev.
- Release branch → manual `deploy-staging` → 24h bake → manual
  `deploy-prod` (different approver).

Databricks shows the deployed app URL in the workspace. Share that
URL with users.

## Step 8 — observe

- **App logs**: Databricks captures stdout/stderr per app run.
- **App metrics**: serverless compute metrics in the Databricks Apps
  page.
- **Audit access**: every SELECT the app runs is logged to
  `system.audit.access_events` under the app's service principal.

## Common mistakes

| Mistake | What goes wrong | Fix |
|---|---|---|
| Business logic in `app.py` | Can't unit-test the data access. | Move queries to `data.py`. |
| Hardcoded warehouse ID | App breaks across environments. | Use `app.yaml` env + `bundle.yml` resource ref. |
| Reading PII directly | Bypasses column masks. | Trust UC — read via the SP, masks apply automatically. |
| Using `st.session_state` for auth | User identity is forgeable. | Read identity from request headers, not session state. |
| Adding a `notebooks/` folder | Not how apps work. | Delete it. The pre-commit hook will eventually catch this. |
| Big static files in the repo | Slows clones. | Put images > 500 KB in S3 + reference by URL. |

## Checklist

- [ ] Picked a framework (default Streamlit)
- [ ] Scaffolded with `just new-app … --kind app`
- [ ] `app.yaml` written with command + env vars
- [ ] `bundle.yml` declares the app + permissions group
- [ ] All data queries live in `data.py`, unit-tested
- [ ] No `notebooks/` folder in the project
- [ ] No business logic in `app.py`
- [ ] User identity read from request headers
- [ ] CODEOWNERS rule for the team
- [ ] `data-architecture.md` row added if the app reads tables
      that weren't read before
- [ ] Smoke-tested in dev before MR-ing to staging

## See also

- `create-a-new-project.md` — the general project-creation flow
- `lakebase-sync-design.md` — pairing apps with Lakebase
- `best-practices/notebooks.md` — what `src/` and `notebooks/` are for
