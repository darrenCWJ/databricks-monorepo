# ADR-0003: Standardized shared library layout (src + notebooks)

- **Status**: Accepted
- **Date**: 2026-06-05
- **Deciders**: Platform team

## Context

Shared libraries under `libs/` serve two audiences:

1. **Other Python code** (projects, scripts, other libs) that `import` functions
2. **Databricks notebooks** that use `sys.path.append` + `import` to call lib code

The first lib (`de_toolbox`) used a flat layout where the package directory IS
the import root. Notebooks, tests, pyproject.toml, and source coexist. This
works but has downsides:

- Tests are importable alongside library code (namespace pollution)
- No clear boundary between "library function" and "notebook entry point"
- Package builds include non-code files (AGENTS.md, pyproject.toml)
- Agents cannot distinguish logic from glue without reading every file
- `[tool.hatch.build.targets.wheel] packages = ["."]` is fragile

## Decision

All shared libraries MUST use the following canonical structure:

```
libs/<lib_name>/
├── pyproject.toml           # packages = ["src/<lib_name>"]
├── AGENTS.md                # lookup tables, rules, local dev
├── README.md                # human-facing docs
├── src/
│   └── <lib_name>/          # THE importable package
│       ├── __init__.py
│       └── ...modules...
├── notebooks/               # Databricks notebook entry points (thin shims)
│   └── ...                  # optional — only if lib has notebook entry points
└── tests/                   # pytest-compatible local tests
    ├── __init__.py
    └── test_*.py
```

### Rules

1. **`src/<lib_name>/`** contains ONLY importable Python modules. No notebooks,
   no configs, no markdown, no test code.

2. **`notebooks/`** contains Databricks notebook shims (optional — only for libs
   that have their own runnable entry points like jobs or housekeeping scripts).
   Each shim is ≤10 lines:
   ```python
   # Databricks notebook source
   import sys
   sys.path.append("/Workspace/Repos/shared/mono-dev/libs/<lib_name>/src")
   from <lib_name>.module import function
   # COMMAND ----------
   function(spark, dbutils, ...)
   ```

3. **`tests/`** at the lib root contains pytest-runnable local tests. Tests that
   require a live Databricks cluster go in `notebooks/tests/` and are marked
   `@pytest.mark.integration`.

4. **All public functions** take `spark` and/or `dbutils` as explicit parameters
   (per ADR-0002). No module-level globals, no `from databricks.sdk.runtime import *`.

5. **`pyproject.toml`** uses:
   ```toml
   [tool.hatch.build.targets.wheel]
   packages = ["src/<lib_name>"]
   ```

6. **Imports within the package** are always fully-qualified:
   `from <lib_name>.submodule import thing` (never bare `from submodule import`).

### Consumer usage

In a Databricks notebook:
```python
import sys
sys.path.append("/Workspace/Repos/shared/mono-dev/libs/<lib_name>/src")
from <lib_name>.module import function
```

In a project's Python code (installed via uv workspace):
```python
from <lib_name>.module import function
```

### Creating a new library

```bash
make new-lib NAME=my-lib-name
```

Then follow the checklist in `libs/README.md`.

## Considered alternatives

### Keep flat layout (current de_toolbox pattern)

- **Pro**: Simpler directory tree, one `sys.path.append` exposes all libs.
- **Con**: Tests importable by consumers, no build isolation, agents can't
  distinguish logic from glue, `packages = ["."]` is fragile. Rejected for
  new libs.

### Monorepo-wide `src/` directory

One `src/` at the repo root containing all libs (e.g., `src/de_toolbox/`,
`src/de_databricks/`).

- **Pro**: Single `sys.path.append` for all libs.
- **Con**: Breaks per-lib isolation, makes `make affected` and CODEOWNERS
  harder, collapses all libs into one tree. Rejected.

### Namespace packages (no `__init__.py`)

- **Pro**: Modern Python packaging pattern.
- **Con**: `sys.path.append` in Databricks doesn't handle namespace packages
  well — explicit `__init__.py` files are more reliable in this environment. Rejected.

## Consequences

**Positive**

- Clean package builds (only `src/` contents in wheel)
- Tests cannot be accidentally imported by consumers
- Clear agent heuristic: `src/` = logic, `notebooks/` = glue
- Consistent pattern across all current and future libs
- Local pytest runs without Databricks runtime for `tests/` directory

**Negative**

- `sys.path.append` in notebooks must point to `libs/<name>/src` (one extra path segment)
- Slightly deeper directory nesting
- Consumer notebooks need updating when migrating from flat layout

## Migration path

- **de_toolbox**: migrate from flat to `src/` layout (this PR)
- **de_databricks**: built with `src/` layout from day one (this PR)
- **Future libs**: MUST use `src/` layout (enforced by `make new-lib` scaffold)

## Compliance

- Consistent with ADR-0001 (agent-friendly, testable, CI-able)
- Consistent with ADR-0002 (explicit `spark`/`dbutils` params)
- Consistent with `libs/README.md` naming conventions

## Revisit triggers

- If uv workspace resolution eliminates need for `sys.path.append`
- If Databricks adds native monorepo package resolution
- If the team adopts a build tool (Pants, Bazel) that handles src layouts natively
