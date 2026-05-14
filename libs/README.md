# libs/

Shared code reused by 2 or more apps. Each library is its own Python
package, published to the workspace as an editable install.

Libraries are **rare**. If only one app uses some code today, inline it
there. Promote to `libs/` only when a second app needs the same code.

## Folder naming

| Pattern | Use when |
|---|---|
| `libs/<team>-common/` | Code only that team's apps use. |
| `libs/common-<thing>/` | Code used across multiple teams. |

## What goes in a lib folder

| File / folder | What |
|---|---|
| `AGENTS.md` | Library-specific rulebook. |
| `pyproject.toml` | Package metadata + dependencies. |
| `src/<package>/` | Production code. |
| `tests/` | Unit tests — coverage targets are stricter for libs (≥90%). |

## Adding a new library

```bash
just new-lib <team>-common
```

Then add it to root `pyproject.toml` workspace members.

## What this folder is NOT for

- One-off helpers used by a single app.
- Code that imports from any specific app (libs must not depend on apps).
