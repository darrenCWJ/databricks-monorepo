# Shared Libraries

Reusable Python packages for the CDO data platform. Each folder under `libs/`
is a self-contained, importable Python package.

## Quick Start

### In a Databricks notebook

Libs are installed onto the job's compute as wheels, so you just import:

```python
from de_toolbox.pipeline.copper import create_copper_table
from de_databricks.common.session import create_databricks_session
```

### In a Databricks Job (databricks.yml)

The consuming bundle builds the wheel from source at its own pinned git ref and
attaches it to the task (ADR-0006):

```yaml
artifacts:
  de_toolbox:
    type: whl
    path: ../../../libs/de_toolbox
    build: uv build --wheel

resources:
  jobs:
    <job_name>:
      tasks:
        - task_key: <task>
          notebook_task:
            notebook_path: ./notebooks/<notebook>.py
          libraries:
            - whl: ../../../libs/de_toolbox/dist/*.whl
```

Also declare the lib in the project's `pyproject.toml` dependencies — that is what
`make affected` reads for blast radius and what `check_lib_deps.py` enforces.

**Never `sys.path.append` to a workspace path.** One shared copy means promoting
one project silently changes the library under every other project in that
workspace. CI fails on it.

### Exploring a lib interactively

Inside a Databricks Git Folder, for exploration only:

```python
%pip install -e /Workspace/Repos/<your-user>/mono-dev/libs/de_toolbox
dbutils.library.restartPython()
```

### In local development / pytest

```bash
# From mono-dev root:
make test P=libs/de_toolbox
make test P=libs/de_databricks
```

## Available Libraries

| Package | Description | Docs |
|---------|-------------|------|
| `de_toolbox` | Databricks pipeline library — medallion layers, Data Vault, Kimball, DQ, profiling, connectors | [AGENTS.md](de_toolbox/AGENTS.md) |
| `de_databricks` | Databricks workspace admin toolkit — IAM, Unity Catalog, housekeeping, Tableau sync | [AGENTS.md](de_databricks/AGENTS.md) |

## Library Layout (ADR-0003)

All libs use the `src/` layout. See `docs/adr/0003-shared-library-layout.md`.

```
libs/<lib_name>/
├── pyproject.toml              # packages = ["src/<lib_name>"]
├── AGENTS.md                   # agent lookup tables + rules
├── README.md
├── src/
│   └── <lib_name>/             # THE importable package
│       ├── __init__.py
│       └── ...modules...
├── notebooks/                  # Databricks notebook shims (optional)
│   └── ...
└── tests/                      # local pytest tests
    └── test_*.py
```

Each lib is built as a wheel by the bundle that consumes it (ADR-0006), so a
notebook imports it directly with no path manipulation. The project's git ref is
the library version — there is no separate version pin.

## Naming convention

| Context | Format | Example |
|---------|--------|---------|
| Folder / import path | underscore | `libs/de_toolbox`, `from de_toolbox import ...` |
| pyproject.toml `name` | hyphen | `"de-toolbox"` |
| pyproject.toml dependency | hyphen | `dependencies = ["de-toolbox"]` |
| Make commands | underscore (folder path) | `make test P=libs/de_toolbox` |

Python normalizes hyphens and underscores in package names — `de-toolbox` and
`de_toolbox` resolve to the same package. Use **underscore** for file paths and
imports, **hyphen** for dependency declarations.

## Adding a new library

```bash
make new-lib NAME=my-lib-name
```

Then:
1. Add an `AGENTS.md` with lookup tables (see `de_toolbox/AGENTS.md` as example)
2. Register in root `pyproject.toml` workspace members
3. Update the table above in this README
4. Update `libs/AGENTS.md` available libraries table

## Declaring a lib dependency (for blast radius tracking)

When a project uses a library, add it to that project's `pyproject.toml`:

```toml
# projects/<domain>/<project-name>/pyproject.toml
[project]
name = "pipeline-accounts"
dependencies = [
    "de-toolbox",    # <-- declare the dependency
    "pyspark>=3.5",
]
```

This enables `make affected` to detect blast radius when the lib changes:
- Any change to `libs/de_toolbox/` will flag all projects that declare
  `de-toolbox` in their dependencies
- Transitive lib-to-lib dependencies are also tracked
- CI notifies CODEOWNERS of affected projects automatically

```bash
# Check blast radius before merging lib changes:
make affected
```

Example output when `libs/de_toolbox/` is modified:
```json
{
  "libs": ["de_toolbox"],
  "projects": ["finance/pipeline-accounts", "hcm/pipeline-workday"],
  "downstream_affected": {
    "lib_transitive": ["fraud/pipeline-alerts"]
  }
}
```

## Rules

1. Only create a lib when code is shared by 2+ projects. Inline otherwise.
2. API changes go in a dedicated MR; consumer notebooks update separately.
3. Every lib must have its own `AGENTS.md` with import lookup tables.
4. Every consuming project MUST declare the lib in its `pyproject.toml` dependencies.
5. Run `make affected` before merging lib changes to see blast radius.
