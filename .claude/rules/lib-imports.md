# Library Import Rules

## How libs reach a Databricks job

Shared libraries are **built as wheels by the bundle that consumes them** and
installed onto the job's compute. There is no shared workspace path.

See `docs/adr/0006-libs-as-bundle-built-wheels.md` for why.

### In the notebook — just import

```python
from de_toolbox.pipeline.copper import create_copper_table
from de_databricks.common.session import create_databricks_session
```

**No `sys.path.append`. Ever.** A `sys.path.append` pointing at a workspace path
is a bug: it silently couples every project in the workspace to one library copy,
so promoting one project changes the library under projects that were never
deployed or tested. CI fails on it.

### In `projects/<domain>/<name>/databricks.yml` — declare and attach

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

Declare only the libs the project actually imports.

### In `projects/<domain>/<name>/pyproject.toml` — MANDATORY

```toml
[project]
dependencies = [
    "de-toolbox",      # <-- MANDATORY when importing de_toolbox
    "de-databricks",   # <-- MANDATORY when importing de_databricks
]
```

This is what `make affected` reads to compute blast radius, what
`check_lib_deps.py` enforces, and what the `artifacts` block is generated from.
All three must agree: import, `pyproject.toml` dependency, `databricks.yml`
artifact.

## Versions

**There is no version pin.** The project's git ref *is* the library version —
one ref names one consistent set of project code and library code, which is what
makes an atomic lib-plus-consumers change possible in a single MR.

Consequence worth holding onto: two projects can legitimately run different
builds of the same lib in production at once, because they are pinned to
different refs. So **a lib must stay backward compatible for at least
`rollback_depth_days`.** A breaking change is a coordinated multi-project change
and goes in its own MR, consumers updated separately (see `AGENTS.md` rule 2).

## Interactive development in a notebook

Inside a Databricks Git Folder, for exploration only:

```python
%pip install -e /Workspace/Repos/<your-user>/mono-dev/libs/de_toolbox
dbutils.library.restartPython()
```

Editable, scoped to your notebook session, invisible to everyone else. Local
development needs nothing — the uv workspace already resolves `libs/*` for
`pytest` and `mypy`.

## Why use a shared lib at all

Shared libs encode **team-validated patterns**: session management, OAuth flows,
SCIM operations, UC permissions, medallion transforms, notification templates —
hardened through production use. Re-implementing them introduces inconsistency,
misses handled edge cases (environment detection, token rotation), and creates
maintenance burden when platform APIs change.

**Always check `make list-libs` before writing utility code.**

## Unresolved imports are blockers

Every import must trace to one of:

1. A shared lib under `libs/<name>/src/`, declared in `pyproject.toml` and
   attached in `databricks.yml`
2. The project's own `src/` package
3. A pip dependency declared in `pyproject.toml`

Anything else is migration debt. Do not proceed — ask the user which repo it
comes from and resolve it first.

## Known gap

Task `libraries` covers **jobs and DLT pipelines**. Databricks **Apps and
serverless** resolve dependencies from `requirements.txt` instead and need a
different mechanism. Unsettled — raise it before shipping the first `app` or
`api` project.

## Quick reference

| Lib package | `pyproject.toml` name | What it provides |
|---|---|---|
| `de_toolbox` | `"de-toolbox"` | Medallion pipeline, Data Vault, Kimball, DQ, connectors |
| `de_databricks` | `"de-databricks"` | Workspace admin: IAM, Unity Catalog, housekeeping, Tableau |
