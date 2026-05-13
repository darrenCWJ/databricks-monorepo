# ADR-0001: Agent-friendly monorepo on uv + DAB

- **Status**: Accepted
- **Date**: 2026-05-11
- **Deciders**: Platform team, ML platform, analytics engineering leads

## Context

Migrating to Databricks across a polyglot codebase (Python, Scala, SQL/dbt).
Need a code home that survives the migration and serves AI coding agents well.

## Decision

One monorepo, native per-language toolchains, DAB as the deploy unit,
`justfile` as the single command surface, `AGENTS.md` per folder.

## Considered alternatives

- **Bazel** — rejected: too expensive at 10-50 engineers
- **Pants** — strongest competitor; revisit if we cross 75 engineers
- **Nx** — rejected: JS-first, polyglot is second-class

See the full report (`agent-friendly-monorepo.md`) for the scorecard.

## Consequences

**Positive**
- Agents use vocabulary they already know (uv, sbt, dbt, databricks bundle)
- Migration is incremental — strangler fig over ~20 weeks
- DABs map 1:1 to deploy units, simplifying promotion

**Negative**
- No remote build cache out of the box; rely on path-filter CI
- Cross-language change-impact is heuristic, not graph-based
- Workspace lockfile changes touch all packages — review carefully

## Revisit triggers

- Engineering headcount > 75
- PR CI time > 15 min after path filters
- Cross-language change-impact becomes a daily problem
