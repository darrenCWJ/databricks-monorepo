# projects/ — Databricks Asset Bundles

## What goes here
One subdirectory per business domain, each containing deploy units grouped by function type.
Each project is a Databricks Asset Bundle (DAB) with its own `bundle.yml`.

## Structure
```
projects/
├── <domain>/                          # Business domain (finance, hcm, infra, ...)
│   ├── <function>-<subdomain>/        # Project directory
│   │   ├── AGENTS.md
│   │   ├── bundle.yml
│   │   ├── pyproject.toml
│   │   ├── notebooks/ or app/
│   │   ├── src/<package>/
│   │   └── tests/
```

## Naming convention
`<function>-<subdomain>-<wildcard>`

- **function** (required): pipeline, streaming, app, dashboard, api, sync, capture
- **subdomain** (required): what it operates on
- **wildcard** (optional): disambiguation suffix (daily, v2, batch)

Examples:
- `projects/finance/pipeline-accounts-payable/`
- `projects/hcm/pipeline-employee-history/`
- `projects/finance/app-budget-viewer/`
- `projects/finance/sync-customer-360/`
- `projects/infra/capture-audit-events/`

## Function types

| Function | Purpose | Template |
|----------|---------|----------|
| pipeline | Batch ETL, orchestration, ingestion | notebooks/ + src/ |
| streaming | Real-time / continuous processing | continuous job |
| app | Web apps (Streamlit, Dash, Flask) | app/ + src/ |
| dashboard | BI dashboards / Lakeview | .lvdash.json |
| api | REST/HTTP service endpoints | FastAPI + app/ |
| sync | Low-latency read (Lakebase sync) | lakebase/ |
| capture | Operational capture (CDC/events) | notebooks/ + src/ |

## Schema contracts (`contracts/schema.yml`)

Every project that writes output tables must declare its schema:

```yaml
models:
  - name: gold.payment_recon
    columns:
      - name: transaction_id
        data_type: STRING
        meta:
          pii: false
          classification: Official-Open
      - name: amount
        data_type: DECIMAL(18,2)
        meta:
          pii: false
          classification: Official-Closed
```

Breaking changes (drop column, rename, type change) are detected by
`check_schema_breaking.py` and block the commit if downstream consumers exist.

## Runtime Dependencies (in AGENTS.md)

Declare runtime dependencies on other projects:

```markdown
## Runtime Dependencies
- reads: projects/finance/sync-customer-360 (table: customer_data.customer_360)
- calls: projects/finance/api-rates-service (endpoint: GET /rates/latest)
```

These are parsed by `build_dep_graph.py` and included in `make affected` output.

## Rules
1. One project = one team's concern. Never edit across project boundaries in one PR.
2. Business logic goes in `src/`, not notebooks. Notebooks are thin shims.
3. Every project must have `AGENTS.md` (≤80 lines) describing purpose, I/O, SLA.
4. Every project with output tables must have `contracts/schema.yml`.
5. Tests must pass locally before opening an MR (`make test P=projects/<domain>/<name>`).
6. No secrets in code. Use Databricks secret scopes via `${secrets.scope.key}`.

## Creating a new project
```bash
make new-project DOMAIN=finance FUNCTION=pipeline NAME=accounts-payable KIND=python
```

## Deploying
```bash
make bundle-validate P=projects/<domain>/<name>
make bundle-deploy P=projects/<domain>/<name> T=dev
make bundle-run P=projects/<domain>/<name> JOB=<task_key> T=dev
```
