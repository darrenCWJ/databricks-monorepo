# Databricks Job — File Layout

## Directory structure

```
apps/<team>-<verb>-<noun>/
├── AGENTS.md
├── bundle.yml
├── pyproject.toml
├── notebooks/
│   └── run.py         # Thin shim — no business logic, <20 lines
├── src/<package>/
│   ├── __init__.py
│   └── job.py         # All business logic here — unit-testable
└── tests/
    └── test_job.py    # pytest, @pytest.mark.unit
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
    run_as:
      service_principal_name: ${var.staging_sp}
  prod:
    workspace:
      host: ${var.databricks_host}
    run_as:
      service_principal_name: ${var.prod_sp}

resources:
  jobs:
    <name>:
      name: <name>
      schedule:
        quartz_cron_expression: "0 0 6 * * ?"
        timezone_id: Asia/Singapore
      job_clusters:
        - job_cluster_key: main
          new_cluster:
            node_type_id: ${var.cluster_node_type_id}
            spark_version: ${var.spark_version}
            num_workers: 2
      tasks:
        - task_key: run
          job_cluster_key: main
          spark_python_task:
            python_file: ./notebooks/run.py
            parameters:
              - "--catalog"
              - "{{job.parameters.catalog}}"
      email_notifications:
        on_failure:
          - ${var.oncall_email}
```

## notebooks/run.py (shim template)

```python
import argparse
from <package>.job import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    args = parser.parse_args()
    run(catalog=args.catalog)
```

Keep this file under 20 lines. All logic goes in `src/<package>/job.py`.
