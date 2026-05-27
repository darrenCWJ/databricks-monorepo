# ADR Template

Create `docs/adr/00NN-migrate-<name>.md`. Increment `NN` from the highest existing ADR number.

```markdown
# 00NN: Migrate <name> into Monorepo

## Status
Accepted

## Context
<Why this is being migrated. What it does. Where it lived before — include the legacy repo URL or file path.>

## Decision
Migrate to `apps/<name>` as a Databricks Asset Bundle (<Job | Databricks App>).

## Residual risks
- <Schema changes that downstream consumers must handle>
- <Shadow-run period and validation approach>
- <Known gaps not addressed in this migration>

## Owner
@cdo/<team>
```

**This ADR is required for all migrations.** It is the SOC2 audit evidence that a deliberate decision was made to bring the code into the platform. `@cdo/data-governance` will reference it during quarterly reviews.
