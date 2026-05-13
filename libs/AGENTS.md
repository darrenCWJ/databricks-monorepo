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

## Rules
1. Only create a library when code is shared by 2+ apps. Inline otherwise.
2. API changes go in a dedicated PR; consumer apps update separately.
3. Platform-wide libs (`common-*`, `testing-utils`) are owned by `@cdo/platform-team`.
4. Team-private libs (`<team>-common`) are owned by the respective team.

## Creating a new library
```bash
just new-lib <name>
```

After creation, register in root `pyproject.toml` under `[tool.uv.workspace] members`.

## Testing
```bash
just test libs/<name>
```
