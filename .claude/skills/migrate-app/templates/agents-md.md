# AGENTS.md Template

Copy this into `projects/<domain>/<name>/AGENTS.md` and fill in every placeholder. Keep under 80 lines.

```markdown
# <app-name>

<One paragraph: what this app does, why it exists, what business process it serves.>

## Owner
@cdo/<team>

## Inputs
- `${catalog}.<schema>.<table>` — <what it reads and why>

## Outputs
- `${catalog}.<schema>.<table>` — classification: Official|Restricted, SLA: <e.g. T+1 by 08:00 SGT>, <what it writes>

## Schedule
<cron expression with timezone, e.g. "0 0 6 * * ? (06:00 SGT daily)">
or: triggered by upstream job `<job-name>`

## Rules
- No business logic in shim files — all logic lives in src/<package>/
- <app-specific invariant, e.g. "never backfill more than 30 days">
- <data invariant, e.g. "use Decimal for all monetary values, never float">
## Runtime Dependencies
- reads: projects/<domain>/<project> (table: <catalog.schema.table>)
- calls: projects/<domain>/<project> (endpoint: <METHOD /path>)
```

**Filling in Inputs / Outputs is mandatory.** `make data-map` reads these sections to build the platform architecture catalogue. If either section is empty, the app will not appear in the data map and `make check-data-map` will fail in CI.

**Runtime Dependencies** are required if this project calls another project's API or reads its Lakebase table at runtime. `make dep-graph` traces these edges. `make affected` flags dependents when a project changes.
