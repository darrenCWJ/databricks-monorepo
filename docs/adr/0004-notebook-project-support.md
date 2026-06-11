# ADR-0004: First-class notebook-only projects

- **Status**: Accepted
- **Date**: 2026-06-10
- **Deciders**: Platform team

## Context

Teams building pipelines, streaming jobs, and Lakebase transforms author logic directly in Databricks notebooks. The monorepo originally mandated src/ layout for all projects (notebooks were thin shims calling src/). This created friction: teams had to wrap simple pipeline code in a Python package with pyproject.toml, tests, and uv workspace registration just to pass CI, even when the code ran exclusively on a Databricks cluster.

## Decision

Support two project styles:

1. `notebook` (default for pipeline/streaming/capture) — logic lives in notebooks/, minimal pyproject.toml declares lib deps only, no src/, no tests/, not a uv workspace member.
2. `src` (default for app/api/dashboard/sync) — existing pattern with src/ package, full pyproject.toml, tests, uv workspace member.

Lint enforcement is the same for both styles, with only Databricks-runtime false positives suppressed for notebooks:

- ruff: F821 (dbutils/spark), E402 (cell imports), I001 (cell sorting)
- ruff format: excluded for notebooks (Databricks serialization format)
- mypy: name-defined, no-untyped-def, type-arg suppressed for projects.*

All security rules, bug detection, and real type errors remain enforced.

## Considered alternatives

- **Exclude notebooks from linting entirely** — rejected: drops code quality, misses real bugs.
- **Force all projects to use src/** — rejected: creates unnecessary friction for simple pipelines.
- **Custom mypy plugin for Databricks** — rejected: maintenance burden, stubs are incomplete anyway.

## Consequences

**Positive**

- Teams can onboard simple pipelines without packaging overhead.
- CI passes for notebook-only projects without per-project config hacks.
- Blast radius tracking still works (minimal pyproject.toml declares deps).

**Negative**

- Notebook code is harder to unit test (no src/ to import in pytest).
- Complex logic in notebooks should eventually graduate to src/ for testability.

## Migration path

When a notebook-only project needs unit testing or shares logic with other projects, refactor to src-wrapped style.
