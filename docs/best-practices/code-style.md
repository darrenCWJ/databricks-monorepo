# Code style

> Conventions that apply across every project. Project-specific overrides
> live in `apps/<name>/AGENTS.md`.

## Python

- **PEP 8 via ruff.** Run `just lint` before every commit. Pre-commit
  runs it on push, too.
- **Type annotations on every public function.** Internal helpers can
  infer, but anything that crosses a module boundary is typed.
- **`from __future__ import annotations`** at the top of every file.
  Saves the runtime cost of evaluating type expressions.
- **No `*` imports.** Spell out what you import.
- **No mutable default arguments.** `def f(x: list = [])` is forbidden —
  use `None` and initialise inside.
- **f-strings only.** No `%` formatting, no `.format()`.
- **Path operations via `pathlib`.** No `os.path.join` in new code.
- **`Decimal` for money.** Never `float`. The pre-commit `boundary-check`
  hook flags floats in any `currency_*` or `amount_*` field.

### File layout

```
apps/<name>/
├── src/<package>/
│   ├── __init__.py          # exports public API
│   ├── transforms.py        # pure transforms — unit-testable
│   ├── io.py                # Spark reads / writes — integration-tested
│   ├── schemas.py           # explicit StructTypes
│   └── _main.py             # entrypoint: orchestration only
├── tests/
│   ├── unit/                # mirrors src/
│   └── integration/         # Spark fixtures
├── notebooks/               # thin shims — see notebooks.md
└── bundle.yml
```

## Scala

- **`scalafmt` for formatting.** Config lives at repo root.
- **`scalastyle` for static checks.**
- **No `var` outside of `private` accumulator state.** Prefer `val` and
  immutable collections.
- **`Option`, `Either`, `Try` over null / exceptions** for expected
  failure modes.
- **`Spark Dataset[T]` over `DataFrame`** when you control the schema —
  the type system catches more.

## SQL (Spark SQL written in PySpark / dbutils.notebook)

- **Lowercase keywords** (`select`, `from`, `where`).
- **Trailing comma style** in column lists — diff-friendly.
- **One predicate per line** in `where`.
- **CTEs over nested subqueries** for anything > 2 levels deep.
- **No `select *` in production code** — name the columns.

## Naming

| Thing | Convention | Example |
|---|---|---|
| Python module | `snake_case` | `payment_recon.py` |
| Python class | `PascalCase` | `PaymentReconciler` |
| Python function | `snake_case` | `compute_daily_totals` |
| Constant | `UPPER_SNAKE` | `DEFAULT_RETENTION_DAYS` |
| Catalog table | `snake_case` plural | `payments`, `customer_dim` |
| Catalog column | `snake_case` | `customer_id`, `created_at_utc` |
| DAB job | `<team>-<verb>-<noun>` | `finance-recon-payments` |

## What we deliberately do NOT do

- **No design patterns for the sake of patterns.** No `*Factory`,
  `*Strategy`, `*Builder` unless they're load-bearing.
- **No abstract base classes with single implementations.** Add an ABC
  when you have two implementations, not before.
- **No project-specific helpers in `libs/`.** Promote only when 2+ apps
  use it.
