# libs/ — Shared Python libraries

## What goes here
Internal Python packages reused by 2+ apps. Imported as workspace
dependencies via `pyproject.toml` `[tool.uv.sources]`.

## Structure per library
```
libs/<name>/
├── AGENTS.md
├── pyproject.toml
├── src/<package>/
│   ├── __init__.py
│   └── ...
└── tests/
```

## AGENTS.md template for each lib

Every lib must have its own `AGENTS.md` with a `## Provides` section.
This is read by `make list-libs` to surface the lib to new apps and migrations.

```markdown
# <lib-name>

<One paragraph: what this library provides and why it exists.>

## Owner
@cdo/<team>

## Provides
- `<package>.<module>.<function>` — <what it does, when to use it>
- `<package>.<module>.<class>` — <what it does, when to use it>

## Consumers
- apps/<app-name> — <why it uses this lib>

## Rules
- <constraints, e.g. "no Spark imports — pure Python only">
- <e.g. "semver versioning — bump minor for new public functions">
```

Run `make list-libs` to see all registered libs and what they expose.

## Rules
1. Only create a library when code is shared by 2+ apps. Inline otherwise.
2. API changes go in a dedicated PR; consumer apps update separately.
3. Platform-wide libs (`common-*`, `testing-utils`) are owned by `@cdo/platform-team`.
4. Team-private libs (`<team>-common`) are owned by the respective team.

## Creating a new library
```bash
make new-lib NAME=<name>
```

After creation, register in root `pyproject.toml` under `[tool.uv.workspace] members`.

## Testing
```bash
make test P=libs/<name>
```
