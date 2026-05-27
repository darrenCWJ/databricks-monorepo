# 0002: Demo Medallion Pipeline

## Status
Accepted

## Context
Demo app to validate the `migrate-app` skill and the monorepo scaffold.
Implements a classic bronze/silver/gold medallion architecture over a
synthetic sales orders dataset. No legacy predecessor — this is greenfield
within the monorepo.

## Decision
Create `apps/demo-ingest-medallion` as a Databricks Asset Bundle with:
- Three notebooks as thin shims (bronze, silver, gold)
- All business logic in `src/demo_ingest_medallion/`
- Unit tests covering quality rules and revenue calculation

## Residual risks
- Landing zone paths (`dbfs:/<catalog>/landing/`) must be pre-provisioned
  before the first run. The job will fail cleanly if paths are missing.
- Gold is full-refresh — do not schedule downstream reads within the
  2-minute overwrite window.

## Owner
@cdo/platform-team
