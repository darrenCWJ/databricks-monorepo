# Library Import Rules

## When importing from libs/

Any time you add `from de_toolbox import ...` or `from de_databricks import ...`
(or any `libs/` package) to a project under `projects/`, you MUST also add it
to that project's `pyproject.toml` dependencies:

```toml
# projects/<domain>/<name>/pyproject.toml
[project]
dependencies = [
    "de-toolbox",      # <-- MANDATORY when importing de_toolbox
    "de-databricks",   # <-- MANDATORY when importing de_databricks
]
```

## Why use shared libraries (not just convenience)

Shared libs encode **team-validated patterns**: session management, OAuth flows,
SCIM operations, UC permissions, medallion transforms, and notification templates
that have been hardened through production use. Re-implementing these patterns:
- Introduces inconsistency across projects
- Misses edge cases already handled (e.g., environment detection, token rotation)
- Creates maintenance burden when platform APIs change

**Always check `make list-libs` before writing utility code.**

## Blast radius tracking

`make affected` uses `pyproject.toml` dependency declarations to detect blast
radius when a lib changes. Without the declaration, the project will silently
break when the lib is modified — CI cannot warn the team.

## CI enforcement

`make lint` runs `tools/scripts/check_lib_deps.py` which will FAIL the MR if
a project imports from a lib without declaring it.

## Notebook sys.path.append (required alongside dependency declaration)

```python
# Each lib uses the src/ layout (per ADR-0003):
import sys
sys.path.append("/Workspace/Repos/shared/mono-dev/libs/de_toolbox/src")
sys.path.append("/Workspace/Repos/shared/mono-dev/libs/de_databricks/src")

from de_toolbox.pipeline.copper import create_copper_table
from de_databricks.common.session import create_databricks_session

# You MUST ALSO declare in pyproject.toml for blast radius tracking
```

## Unresolved imports are blockers

Every import must trace to one of:
1. A shared lib under `libs/<name>/src/`
2. The project's own `src/` package
3. A pip dependency declared in `pyproject.toml`

Any `sys.path.append` or bare import that doesn't resolve to one of these three
is **migration debt**. Do not proceed — ask the user which repo it comes from
and resolve it before continuing.

## Quick reference

| Lib package | pyproject.toml dependency name | What it provides |
|---|---|---|
| `de_toolbox` | `"de-toolbox"` | Medallion pipeline, Data Vault, Kimball, DQ, connectors |
| `de_databricks` | `"de-databricks"` | Workspace admin: IAM, Unity Catalog, housekeeping, Tableau |
