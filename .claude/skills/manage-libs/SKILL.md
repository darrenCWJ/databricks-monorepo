---
name: manage-libs
description: Create, edit, or migrate shared libraries under libs/. Enforces ADR-0003 src/ layout, AGENTS.md format, pyproject.toml config, dependency registration, and import conventions. Use when adding a new lib, restructuring an existing one, or bringing external repo code into libs/.
---

# Manage Shared Libraries

Covers three operations on `libs/`:
1. **Create** — new greenfield library
2. **Migrate** — bring external repo code into an existing or new lib
3. **Edit** — add modules, update AGENTS.md, change structure

Done when: code lives in `src/<lib_name>/`, AGENTS.md has import lookup tables,
pyproject.toml builds correctly, workspace registration is complete, and
`libs/README.md` is updated.

---

## Announce-Before-Act

Before every state-changing action, output:
> [Phase N] About to `<action>`: `<reason>`

STOP and wait for confirmation before:
- Creating new directories or files
- Modifying `AGENTS.md`, `pyproject.toml`, or root workspace config
- Deleting or moving existing code

---

## Pre-Flight — Resolve Before Proceeding (MANDATORY)

Present all questions in one message. Do not proceed until resolved.

| # | Item | Required? |
|---|---|---|
| 1 | **Operation** | YES — create / migrate / edit |
| 2 | **Library name** | YES — lowercase, underscore for imports (e.g. `de_databricks`) |
| 3 | **What it does** | YES — one sentence |
| 4 | **Owner** | YES — `@team` or individual handles |
| 5 | **Source location** (migrate only) | YES — repo URL or path |
| 6 | **Has notebook entry points?** | YES — determines if `notebooks/` dir is needed |
| 7 | **Dependencies on other libs** | YES — which other libs does it import from? |

If migrating, also ask:
- "Does the source have imports from external repos I should know about?"
- "Are there notebook-style tests that require a live Databricks cluster?"

---

## Canonical Structure (ADR-0003 — non-negotiable)

```
libs/<lib_name>/
├── pyproject.toml
├── AGENTS.md
├── README.md
├── src/
│   └── <lib_name>/           # THE importable package
│       ├── __init__.py
│       └── <modules...>
├── notebooks/                # ONLY if lib has notebook entry points
│   └── <shims + configs>
└── tests/                    # pytest-compatible local tests
    ├── __init__.py
    └── test_*.py
```

### Hard rules

1. `src/<lib_name>/` contains ONLY importable Python modules
2. No notebooks, JSON configs, markdown, or test code inside `src/`
3. Imports are always fully-qualified: `from <lib_name>.module import func`
4. Never bare imports: `from module import func` is WRONG
5. Public functions take `spark`/`dbutils` as explicit params (per ADR-0002)
6. No `from databricks.sdk.runtime import *` at module level in library code
7. `notebooks/` shims are ≤10 lines — logic lives in `src/`

---

## Phase 1 — Create / Scaffold

### For new libs:

```bash
make new-lib NAME=<lib_name>
```

If `make new-lib` doesn't produce the `src/` layout, create manually:

```bash
mkdir -p libs/<lib_name>/src/<lib_name>
mkdir -p libs/<lib_name>/tests
touch libs/<lib_name>/src/<lib_name>/__init__.py
touch libs/<lib_name>/tests/__init__.py
```

### For migrations:

1. Scan the source for all Python modules
2. Identify which are **library code** (reusable functions) vs **notebook entry points** (orchestration with widgets/globals)
3. Ask the user if unclear: "Is `<file>` library logic or a notebook entry point?"

---

## Phase 2 — Import Resolution (BLOCKER)

Scan all source files for imports. Every import must resolve to one of:
1. Another module within the same lib (`from <lib_name>.submodule import ...`)
2. A declared pip dependency in `pyproject.toml`
3. Another shared lib under `libs/` (declared in dependencies)

**If an import doesn't resolve — STOP and ask:**

> "This code imports from `<module or path>`. Which repo does this come from?
> Options:
> 1. It's in our shared libs already (which one?)
> 2. It's from another repo we own (needs migration)
> 3. It's a pip package (add to dependencies)
> 4. It's small glue code (inline it)"

Do not guess. Do not proceed with unresolved imports.

---

## Phase 3 — pyproject.toml

```toml
[project]
name = "<lib-name>"                    # hyphenated
version = "0.1.0"
description = "<one-line description>"
requires-python = ">=3.11"
dependencies = [
    # Only what the lib actually imports at runtime
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.6",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/<lib_name>"]          # MUST point to src/

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: fast, no external deps",
    "integration: requires a live Databricks connection",
]
```

---

## Phase 4 — AGENTS.md (MANDATORY format)

Every lib MUST have an AGENTS.md with these sections in order:

```markdown
# <lib_name>

<One-line description.>

**Location**: `libs/<lib_name>/src/<lib_name>/`
**Import path**: `from <lib_name>.<module> import <function>`
**Consumed as**: a wheel built by the consuming bundle (ADR-0006). Notebooks just
`import`; the bundle declares an `artifacts` entry and a task `libraries: - whl:`.

## Owner
@<owner_handles>

## Architecture
<Explain src/ vs notebooks/ split. Reference ADR-0003.>

## Folder structure
<Tree diagram showing directory layout>

## Module import lookup
| I need to... | Import |
|---|---|
| <action> | `from <lib_name>.<module> import <func>` |
| ... | ... |

## Rules
- <Rule 1>
- <Rule 2>

## Local dev
```bash
make test P=libs/<lib_name>
make lint P=libs/<lib_name>
```
```

### Import lookup table requirements

- One row per **user intent** (what someone wants to do), not per function
- Group by module area
- Must cover every public function the lib exposes
- Use the exact import statement a consumer would write

---

## Phase 5 — README.md

Short human-facing doc:
- What the lib does (2-3 sentences)
- Quick start code snippet
- Link to AGENTS.md for full reference

---

## Phase 6 — Registration

### Root `pyproject.toml`

```diff
[tool.uv.workspace]
members = [
+    "libs/<lib_name>",
]
```

### Root `pyproject.toml` ruff ignores (if legacy code)

```toml
"libs/<lib_name>/**" = [
    # Add only ignores the code actually needs
]
```

### `libs/README.md`

Add row to the available libraries table:
```
| `<lib_name>` | <description> | [AGENTS.md](<lib_name>/AGENTS.md) |
```

---

## Phase 7 — Tests

### Local tests (`tests/`)

At minimum, a smoke test that verifies the package imports:

```python
def test_package_importable():
    import importlib
    spec = importlib.util.find_spec("<lib_name>")
    assert spec is not None
```

Add real unit tests for any function that doesn't require Databricks runtime.

### Notebook tests (`notebooks/tests/` — optional)

Integration tests that require a live cluster stay in `notebooks/tests/`.
These run via Databricks Jobs, not local pytest.

---

## Phase 8 — Pre-CI Checks

```bash
make lint P=libs/<lib_name>
make test P=libs/<lib_name>
```

Both must pass before opening MR.

---

## Checklist

- [ ] `src/<lib_name>/` contains all importable modules
- [ ] Every subdirectory has `__init__.py`
- [ ] All internal imports are fully-qualified (`from <lib_name>.X import Y`)
- [ ] No unresolved external imports (all asked and resolved)
- [ ] No `from databricks.sdk.runtime import *` at module level
- [ ] Public functions accept `spark`/`dbutils` explicitly
- [ ] `pyproject.toml` has `packages = ["src/<lib_name>"]`
- [ ] `AGENTS.md` has import lookup table covering all public functions
- [ ] `README.md` exists with quick start
- [ ] Registered in root `pyproject.toml` workspace members
- [ ] Added to `libs/README.md` available libraries table
- [ ] `make lint` passes
- [ ] `make test` passes
- [ ] `notebooks/` shims are ≤10 lines each (if applicable)

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Bare imports (`from session import *`) | Always `from <lib_name>.module import *` |
| Tests inside `src/` | Move to `tests/` at lib root |
| `packages = ["."]` in pyproject.toml | Must be `["src/<lib_name>"]` |
| Missing AGENTS.md import lookup table | Add one row per user intent |
| Not registered in workspace members | `make setup` won't resolve it |
| Guessing what an external import is | ASK the user — never assume |
| Notebook logic in `src/` | Extract to `notebooks/` shims |
| JSON configs inside `src/` | Move to `notebooks/` or project-level config |
| No `__init__.py` in subdirectories | Package won't resolve submodules |
| AGENTS.md missing notebook setup line | Consumers won't know the sys.path |
