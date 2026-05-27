# Databricks App — File Layout

## Directory structure

```
apps/<team>-<verb>-<noun>/
├── AGENTS.md
├── bundle.yml
├── pyproject.toml
├── app/
│   ├── app.yaml       # Runtime command + env vars
│   └── app.py         # Thin shim — no business logic, <30 lines
├── src/<package>/
│   ├── __init__.py
│   └── logic.py       # All business logic here — unit-testable
└── tests/
    └── test_logic.py  # pytest, @pytest.mark.unit
```

## app/app.yaml

```yaml
command:
  - streamlit      # swap for: flask, python, node, etc.
  - run
  - app.py
env:
  - name: CATALOG
    valueFrom: catalog-resource   # references a resource name in bundle.yml
  - name: STATIC_VAR
    value: some-value
```

## bundle.yml skeleton

```yaml
bundle:
  name: <name>

variables:
  catalog:
    description: Target Unity Catalog
    default: cdo_dev

targets:
  dev:
    default: true
    workspace:
      host: ${var.databricks_host}
  staging:
    workspace:
      host: ${var.databricks_host}
  prod:
    workspace:
      host: ${var.databricks_host}

resources:
  apps:
    <name>:
      name: "<name>"
      description: "<what this app does>"
      source_code_path: ./app
      compute_size: MEDIUM
      config:
        command: ["streamlit", "run", "app.py"]   # must match app.yaml
        env:
          - name: CATALOG
            value: ${var.catalog}
      resources:
        - name: catalog-resource
          # Use job:, sql_warehouse:, or serving_endpoint: as appropriate
          serving_endpoint:
            id: ${var.serving_endpoint_id}
            permission: CAN_QUERY
      permissions:
        - level: CAN_VIEW
          group_name: ${var.viewer_group}
        - level: CAN_EDIT
          user_name: ${var.owner_email}
```

## app/app.py (shim template — Streamlit example)

```python
import os
import streamlit as st
from <package>.logic import load_data, render_chart

catalog = os.environ.get("CATALOG", "cdo_dev")
df = load_data(catalog=catalog)
render_chart(df)
```

Keep this file under 30 lines. All logic goes in `src/<package>/logic.py`.

## Key differences from a Databricks Job

| | Job | Databricks App |
|---|---|---|
| Entry point | `notebooks/run.py` | `app/app.py` |
| Runtime config | `bundle.yml` tasks | `app/app.yaml` + `bundle.yml` resources.apps |
| Execution | Batch, runs to completion | Long-running web service |
| `run_as:` | Required for staging/prod | Not applicable — app runs as viewer/editor |
| Shadow run | Diff output tables | Side-by-side URL comparison |
| Thin shim limit | <20 lines | <30 lines |
