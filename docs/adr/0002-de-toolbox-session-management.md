# ADR-0002: de-toolbox session and runtime dependency management

- **Status**: Proposed
- **Date**: 2026-06-04
- **Deciders**: Platform team, data engineering leads

## Context

`de_toolbox` is a shared library of reusable Databricks pipeline functions
(medallion layers, Data Vault, Kimball, DQ, profiling). It is being migrated
from a standalone repo into `libs/de_toolbox/` within the monorepo.

The existing codebase has three incompatible patterns for accessing the Spark
session and Databricks utilities:

| Pattern | Used by | Mechanism |
|---------|---------|-----------|
| A: `global spark` mutation | V1 autoloader, copper, data_vault, kimball, DQ | Entry-point function receives `_spark`, assigns to module-level `global spark`. Inner functions reference the bare global. |
| B: Explicit `spark` param | V2 autoloader, common/functions.py, profiling | Every function receives `spark` as its first argument. |
| C: Explicit `spark` + `dbutils` params | V3 autoloader | Both runtime objects passed explicitly to every function. |

Additionally, `dbutils` (Databricks Utilities — secrets, filesystem, jobs) is
handled inconsistently:

- Some functions use `dbutils` as an implicit notebook global (never declared,
  just assumed to exist at call time).
- V3 passes it as a function parameter.
- `from databricks.sdk.runtime import *` pulls it in at import time (works in
  clusters but breaks in local testing).

### Problems with the status quo

1. **Untestable** — Pattern A makes unit testing impossible without monkeypatching
   module-level state. Pattern B/C are testable by passing a mock.
2. **Hidden coupling** — Pattern A callers don't know a function needs Spark until
   it crashes at runtime. The function signature lies about its dependencies.
3. **Agent confusion** — An AI agent reading the code cannot determine from the
   function signature what runtime objects are required. It must read the entire
   call stack.
4. **Thread safety** — Module-level globals are inherently unsafe if multiple
   threads call entry points concurrently (unlikely today, but a future risk with
   concurrent tasks in Databricks Jobs).
5. **dbutils availability** — `dbutils` does not exist outside Databricks clusters.
   Code that assumes it as a global cannot run in `pytest`, CI, or local dev
   without a shim.

## Decision

**Adopt Pattern C (explicit params) as the standard for all public functions in
`libs/de_toolbox/`.**

Specifically:

1. Every public function that needs Spark takes `spark: SparkSession` as its
   **first positional argument**.
2. Every public function that needs Databricks Utilities takes `dbutils` as its
   **second positional argument** (only when actually used — do not pass it
   through layers that never reference it).
3. No module-level `global spark` or `global dbutils` assignments anywhere in
   the library.
4. No `from databricks.sdk.runtime import *` at module level.
5. Internal helper functions that need `spark` receive it from their caller, not
   from a global.
6. Functions that do not need `spark` or `dbutils` (pure logic, validation,
   formatting) must NOT accept them — keep signatures honest.

### Migration shim for backward compatibility

A thin compatibility wrapper will be provided at the package root for callers
that still use the old `create_bronze(_spark, project, ...)` signature:

```python
# de_toolbox/_compat.py
def create_bronze_legacy(_spark, project, metadata_name, env, ...):
    """Backward-compat shim. Prefer create_bronze_table(spark, ...) directly."""
    from de_toolbox.pipeline.bronze import create_bronze_table
    return create_bronze_table(_spark, ...)
```

The `_legacy/` module will re-export these shims. Deprecation warnings will be
emitted. Removal target: 2 release cycles after migration.

### For dbutils specifically

Functions needing only secrets (e.g., `send_email`) will accept a `get_secret`
callable instead of the full `dbutils` object:

```python
def send_email(sender, recipient, subject, body, *, get_secret):
    username = get_secret("cdo_aws_ses", "ses_username")
    password = get_secret("cdo_aws_ses", "ses_password")
    ...
```

Callers in notebooks pass `get_secret=dbutils.secrets.get`. Tests pass a stub.
This avoids importing or depending on `dbutils` at all.

Functions needing filesystem operations (`dbutils.fs`) will accept `dbutils`
directly — there is no clean abstraction over it that saves complexity.

## Considered alternatives

### Keep Pattern A (global mutation)

- **Pro**: Zero migration work for existing callers.
- **Con**: All the testing, readability, and safety problems remain.
  Incompatible with the monorepo's testing requirements (80% coverage target).

### Session registry / singleton

```python
# Hypothetical:
from de_toolbox.session import get_spark
spark = get_spark()  # module-level singleton
```

- **Pro**: Convenient import; no param threading.
- **Con**: Hidden global state with a nicer API. Still untestable without
  monkeypatching. Obscures dependencies from agents reading signatures. Rejected.

### Dependency injection container

- **Pro**: Enterprise-grade DI (e.g., `dependency_injector` library).
- **Con**: Massive over-engineering for a data pipeline library with two runtime
  dependencies (`spark`, `dbutils`). Rejected.

## Consequences

**Positive**
- Every function's dependencies are visible in its signature. Agents and humans
  can reason about requirements without reading implementation.
- Unit tests pass `spark` from `testing_utils.spark_fixture` — no globals, no
  monkeypatch.
- Library is importable and testable outside Databricks (CI, local dev).
- Thread-safe by construction.

**Negative**
- Existing V1 callers must update their notebooks. Mitigation: `_legacy/` shims
  and a `docs/MIGRATION.md` guide.
- Slightly more verbose call sites (`spark` appears in every call). Acceptable —
  explicitness is a feature for a shared library.
- Functions that call many sub-functions must thread `spark` through. Acceptable —
  this is the normal cost of explicit dependency passing.

## Compliance

- Consistent with `mono-dev/.claude/rules/python-databricks.md` (no hardcoded
  credentials, use `dbutils.secrets` in notebooks, env vars in scripts).
- Consistent with ADR-0001 (agent-friendly, testable, CI-able).

## Revisit triggers

- If a `SparkSession` builder becomes standard in the monorepo (e.g., via
  Databricks Connect for all local dev), a module-level factory *may* become
  acceptable — but only as an optional convenience alongside explicit params.
- If `dbutils` is needed in >10 functions, consider a lightweight context
  object bundling `spark` + `dbutils`.
