# libs/ — Shared Python libraries

## What goes here
Internal Python packages reused by 2+ projects. Each library uses the
`src/` layout (per ADR-0003): importable code lives under `libs/<name>/src/<package>/`.

## How to use a lib in a Databricks notebook

```python
import sys
sys.path.append("/Workspace/Repos/shared/mono-dev/libs/de_toolbox/src")
sys.path.append("/Workspace/Repos/shared/mono-dev/libs/de_databricks/src")

from de_toolbox.pipeline.copper import create_copper_table
from de_databricks.common.session import create_databricks_session
```

## Structure per library

```
libs/<lib_name>/              <- Library root (not importable directly)
├── pyproject.toml            <- Package metadata; packages = ["src/<lib_name>"]
├── AGENTS.md                 <- Agent docs (lookup tables, rules)
├── src/
│   └── <lib_name>/           <- THE importable package
│       ├── __init__.py       <- Public API re-exports
│       └── ...modules...
├── notebooks/                <- Thin notebook shims (optional)
└── tests/                    <- pytest tests (outside the package)
```

## AGENTS.md requirements for each lib

Every lib AGENTS.md must have:
1. **Import path** + **notebook setup** at the top
2. **Folder structure** annotated with each file's purpose
3. **Lookup table**: "I need to X" -> exact import + args
4. **Rules** for new code vs legacy

## Available libraries

| Library | Package | Provides | Owner |
|---------|---------|----------|-------|
| de_toolbox | `de_toolbox` | Medallion pipelines, Data Vault, Kimball, DQ, profiling, connectors (Workday/SharePoint), UC permissions | @wei_hao_tan @jeffrey_siew |
| de_databricks | `de_databricks` | Workspace admin: IAM, Unity Catalog, housekeeping, Tableau sync, catalog migration | @wei_hao_tan @jeffrey_siew |

## Blast radius

When a lib is modified, `make affected` reports:
- **Projects** that declare the lib in their `pyproject.toml` dependencies
- **Transitive** libs that depend on the changed lib (full BFS closure)
- **Scripts** in `tools/scripts/` that import the lib package
- **Skills** in `.claude/skills/` that reference the lib

CODEOWNERS for affected projects are automatically notified via CI.

### How consumers declare dependency (MANDATORY)

Every project that uses a lib MUST add it to `pyproject.toml`:

```toml
# projects/<domain>/<name>/pyproject.toml
[project]
dependencies = [
    "de-toolbox",
]
```

Without this declaration, `make affected` CANNOT detect the project as
impacted. Undeclared consumers will silently break on lib changes.

## Rules
1. Only create a library when code is shared by 2+ projects. Inline otherwise.
2. API changes go in a dedicated PR; consumer apps update separately.
3. Consuming projects MUST declare the lib in `pyproject.toml` dependencies.
4. Platform-wide libs (`common-*`, `testing-utils`) are owned by `@cdo/platform-team`.
5. Team-private libs (`<team>-common`) are owned by the respective team.

## Creating a new library
```bash
make new-lib NAME=<name>
```

After creation:
1. Register in root `pyproject.toml` under `[tool.uv.workspace] members`
2. Add `AGENTS.md` with folder structure + lookup tables
3. Update `libs/AGENTS.md` available libraries table
4. Update `libs/README.md` available libraries table

## Testing
```bash
make test P=libs/<name>
```
