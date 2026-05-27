---
name: new-app
description: Use when creating a new greenfield Databricks app or workflow from scratch in the monorepo. Applies when no legacy code exists to migrate — the team knows what they want to build but needs help with structure, scaffolding, registration, Claude/AI context setup, and quality gates.
---

# Create a New App

## Overview

Guides the full lifecycle of a new greenfield app: goal clarification,
libs/skills discovery, design review, scaffold, register, Claude context
setup, and pre-CI gates. Every action is announced before it runs. Every
uncertainty is resolved with the human before any file is written.

**Not this skill:** Migrating existing code into the monorepo — use `migrate-app`.

---

## Announce-Before-Act (applies to every phase)

Before taking any action, state what you are about to do and why:

```
> [Phase X] About to <action>: <brief reason>.
```

| Action type | Rule |
|---|---|
| Read-only scan | Just run — no announcement needed |
| Shell command, file write, registry edit | Announce, then execute |
| Scaffold, source files, commit, deploy | **Stop and wait for explicit confirmation** |

---

## Pre-Flight — Clarify Before Anything (MANDATORY FIRST STEP)

Present all questions in **one message** using the format below.
For each item, show a recommended option and numbered alternatives.
User can reply with a number, type a custom value, or say "skip" for optional items.
Do not proceed until all required items (marked *) are resolved.

---

**Quick setup — reply with a number or type your own:**

**1. App name*** — `<team>-<verb>-<noun>`
> Suggested: `<inferred-from-context>` — confirm or type a new name.
> Format: team prefix + what it does (e.g. `finance-payment-recon`, `infra-data-sync`)

**2. Owner team***
> 1. `@cdo/finance-team` _(recommended based on name prefix)_
> 2. `@cdo/platform-team`
> 3. `@cdo/supplier-team`
> 4. `@cdo/infra-team`
> 5. Other — type team name

**3. What does this app do?*** _(1–2 sentences is enough)_
> e.g. "Reconciles daily payment transactions against bank statements and flags discrepancies."

**4. Inputs*** — tables/sources this app reads
> e.g. `cdo_dev.landing.payments` — or type "unknown" to fill in later

**5. Outputs*** — tables this app produces
> e.g. `cdo_dev.gold.payment_recon` — or type "unknown" to fill in later

**6. Schedule***
> 1. Daily at 02:00 SGT _(recommended)_
> 2. Hourly
> 3. Triggered by upstream job — type job name
> 4. On-demand only
> 5. Other — type cron expression

**7. Language***
> 1. Python _(recommended)_
> 2. Scala

**8. Business rules** _(optional — press Enter or type "none" to skip)_
> e.g. "Never backfill > 30 days", "99.9% completeness SLA by 06:00 SGT"

**9. Claude context** _(optional)_
> Create an app-level `CLAUDE.md` with domain rules for future Claude sessions?
> 1. Yes — create CLAUDE.md _(recommended for complex domain apps)_
> 2. No

---

If any answer introduces new uncertainty, ask again before moving on.

---

## Phase 0 — Discovery (read-only, no changes)

### Step 0a: Show available shared libraries

> [Phase 0] About to run `make list-libs` — checking what shared code already exists before designing the app.

```bash
make list-libs
```

If any lib covers functionality the app will need (e.g. validation helpers,
common transforms, testing utilities), note it. Plan to import it rather
than re-implement.

### Step 0b: Show relevant existing apps for reference

> [Phase 0] Scanning apps/ for apps owned by the same team — useful as structural reference.

```bash
ls apps/ | grep <team-prefix>
```

Surface any similar apps so the new one can follow established patterns.

### Step 0c: Show all available tables from other monorepo apps

> [Phase 0] Reading docs/data-architecture.md — showing what output tables already exist in the repo that this app could read from.

Read `docs/data-architecture.md` and display the full output table list:

```
AVAILABLE TABLES FROM OTHER APPS
─────────────────────────────────────────────────────────────
App                      Owner                  Outputs
<app-name>               @cdo/<team>            <catalog.schema.table>
...
─────────────────────────────────────────────────────────────
Ask: "Does this app need to read from any of these tables?"
```

If yes — note each cross-app dependency. It becomes an Input in AGENTS.md
and must be declared in the Bronze tier (Phase 3) as a source.

**Important:** Reading another app's output table (Delta read) is fine.
Importing another app's Python code is blocked by pre-commit — use `libs/` instead.

### Step 0d: Check CODEOWNERS for existing team wildcard

```bash
grep "/apps/<team>-" CODEOWNERS
```

If a wildcard already covers the new app's name, no new CODEOWNERS line is
needed. Note the result for Phase 6.

---

## Phase 1 — Design Review (HUMAN CONFIRMS BEFORE SCAFFOLD)

Using the answers from Pre-Flight and Phase 0, present the complete
design for human review. **Do not scaffold until explicitly approved.**

```
APP DESIGN REVIEW
─────────────────────────────────────────────────────────────────────
Name         : <team>-<verb>-<noun>
Owner        : @cdo/<team>
Language     : Python | Scala
Goal         : <1-2 sentence description>

Files to create:
  apps/<name>/AGENTS.md          — metadata, I/O, schedule, rules
  apps/<name>/bundle.yml         — DAB job definition
  apps/<name>/pyproject.toml     — Python deps
  apps/<name>/notebooks/run.py   — thin shim
  apps/<name>/src/<pkg>/job.py   — business logic entry point
  apps/<name>/tests/test_job.py  — initial smoke test

I/O:
  Reads  : <catalog.schema.table>, ...
  Writes : <catalog.schema.table>, ...
  Schedule: <cron / trigger>

Libs to import (from make list-libs):
  <lib-name> — <why it applies>   OR   (none — no overlap found)

Registry updates:
  pyproject.toml   — ADD workspace member
  CODEOWNERS       — <ADD line / already covered by wildcard>
  data-architecture.md — REGENERATE after AGENTS.md filled

Claude context:
  <YES — create apps/<name>/CLAUDE.md>   OR   <NO>
─────────────────────────────────────────────────────────────────────
Confirm the design above, or specify corrections.
```

Only proceed after explicit approval.

---

## Phase 2 — Scaffold & Fill

### Step 2a: Run scaffold

> [Phase 2] About to run `make new-app NAME=<name> KIND=<python|scala>` — this creates the folder and stub files.

```bash
make new-app NAME=<name> KIND=python
```

### Step 2b: Fill in stubs immediately

The scaffold produces placeholder TODOs. Fill every stub now using the
Pre-Flight answers — do not leave TODOs in committed files.

**`AGENTS.md`** — replace all TODOs:
```markdown
# <name>

<Goal from Pre-Flight — 1-2 sentences.>

## Owner
@cdo/<team>

## Inputs
- `<catalog.schema.table>` — <what it reads and why>

## Outputs
- `<catalog.schema.table>` — <classification, SLA, what it writes>

## Schedule
<cron expression or "triggered by <upstream-job>">

## Rules
- No business logic in notebooks — logic lives in src/<pkg>/
- <Key business rules from Pre-Flight>
```

**`bundle.yml`** — set targets, schedule, run_as for staging/prod:
```yaml
targets:
  dev:
    default: true
    workspace:
      host: ${var.workspace_host}
    variables:
      catalog: cdo_dev
  staging:
    workspace:
      host: ${var.workspace_host}
    variables:
      catalog: cdo_staging
    run_as:
      service_principal_name: ${var.sp_name}
  prod:
    workspace:
      host: ${var.workspace_host}
    variables:
      catalog: cdo_prod
    run_as:
      service_principal_name: ${var.sp_name}
```

**`src/<pkg>/job.py`** — replace the hello-world stub with the real
entry-point signature, documented with inputs/outputs:
```python
def run(catalog: str) -> None:
    """<What this does in one sentence.>

    Reads : <catalog>.schema.input_table
    Writes: <catalog>.schema.output_table
    """
    ...
```

**`tests/test_job.py`** — replace smoke test with one meaningful unit
test that asserts real behaviour, not just "it ran":
```python
@pytest.mark.unit
def test_<meaningful_name>() -> None:
    # Arrange
    ...
    # Act
    result = run(...)
    # Assert
    assert result ...
```

---

## Phase 3 — Bronze / Ingest Tier

> [Phase 3] Starting Bronze tier design — will ask about the data source before writing any code.

### Step 3a: Understand the source

Ask the user (all in one message):

```
Bronze tier — let's design the ingest layer.

1. Source type  (can select more than one if app reads multiple sources)
   1. REST API
   2. CSV / Parquet file drop
   3. Database (JDBC)
   4. Kafka / streaming
   5. Another monorepo app's output table  ← show list from Phase 0 Step 0c
   6. Other — describe

   If option 5: show the available table list from docs/data-architecture.md
   and ask which table(s) to read from. These are direct Delta reads —
   no ingestion code needed, skip to Silver tier for these inputs.

2. Source details  (for each non-monorepo source)
   - API: endpoint URL, HTTP method, auth type (API key / OAuth / bearer)
   - File: landing path (dbfs:/ or abfss://), format, arrival pattern
   - DB: connection alias, source table or query

3. What does one record look like?
   Paste a sample response / row, or list the fields and their types.
   e.g.  payment_id: string, amount: float, currency: string, ts: timestamp

4. Bronze table name  (for each external source being ingested)
   Recommended: `<catalog>.bronze.<pkg_name>`  — confirm or change
   Note: cross-app reads from option 5 do not need a bronze table.

5. Write mode
   1. Append + partition by ingestion_date  (recommended for most sources)
   2. Full refresh (overwrite)
```

### Step 3b: Present Bronze design — wait for confirmation

```
BRONZE DESIGN
─────────────────────────────────────────────────────────────
External sources (ingested):
  Source : <type> — <endpoint / path>
  Table  : <catalog>.bronze.<name>
  Mode   : <append partitioned by ingestion_date | full-refresh>
  Fields from source:
    <field>   <type>   — as-is from source
    ...
  Added by ingest:
    ingestion_date   date     — run date
    _source          string   — source identifier

Cross-app reads (direct Delta, no ingest needed):
  <catalog.schema.table>   owned by <app-name> (@cdo/<team>)
  ...  — OR —  none
─────────────────────────────────────────────────────────────
Confirm or correct before code is written.
```

### Step 3c: Write Bronze code

After confirmation:
- `src/<pkg>/ingest.py` — fetch + land logic, `ingest_<name>(catalog, run_date)` entry point
- `notebooks/01_ingest.py` — thin shim only
- `tests/test_ingest.py` — unit tests for field mapping and metadata tagging (mock the API/file read)

---

## Phase 4 — Silver / Transform Tier

> [Phase 4] Starting Silver tier design — will show Bronze schema and ask what transformations are needed.

### Step 4a: Show Bronze schema, ask for transformation intent

Display the Bronze table and fields defined in Phase 3, then ask:

```
Silver tier — let's design the transformation layer.
Bronze input: <catalog>.bronze.<name>

Fields available:
  <field1>  <type>
  <field2>  <type>
  ...

Answer the following (all at once):

1. Quality rules — which fields must pass checks to reach silver?
   For each: field name, rule type, action on failure
   Options: NOT NULL, > 0, IN [list], regex match, range [min,max]
   Action: quarantine (keep row in _quarantine table) | drop | fail job
   e.g.  payment_id: NOT NULL → quarantine
         amount: > 0 → quarantine
         currency: IN [SGD, USD, EUR] → quarantine

2. Deduplication — deduplicate rows?
   1. Yes — on which key field(s)? Keep: latest / first
   2. No

3. Derived fields — any new columns to compute?
   e.g.  amount_sgd = amount * fx_rate
   Or type "none"

4. Silver table name
   Recommended: `<catalog>.silver.<pkg_name>`  — confirm or change

5. Quarantine table name (if any rules quarantine)
   Recommended: `<catalog>.silver.<pkg_name>_quarantine`  — confirm or change
```

### Step 4b: Present Silver design — wait for confirmation

```
SILVER DESIGN
─────────────────────────────────────────────────────────────
Input     : <catalog>.bronze.<name>
Output    : <catalog>.silver.<name>
Quarantine: <catalog>.silver.<name>_quarantine

Quality rules:
  <field>  <rule>  → <action>
  ...

Deduplication: on <key>, keep <latest|first> by <timestamp>
  — OR —  none

Derived fields:
  <new_field> = <expression>   (<why>)
  ...

Pass-through: all remaining fields from bronze
─────────────────────────────────────────────────────────────
Confirm or correct before code is written.
```

### Step 4c: Write Silver code

After confirmation:
- `src/<pkg>/silver.py` — quality rules dict, transform function, quarantine split
- `notebooks/02_silver.py` — thin shim only
- `tests/test_silver.py` — unit tests: one passing row, one row per failing rule, dedup behaviour

---

## Phase 5 — Gold / Serving Tier

> [Phase 5] Starting Gold tier design — will show Silver schema and ask what the business wants to see.

### Step 5a: Show Silver schema, ask for business output intent

Display the Silver table and fields defined in Phase 4, then ask:

```
Gold tier — let's design the serving layer.
Silver input: <catalog>.silver.<name>

Fields available:
  <field1>  <type>
  <field2>  <type>
  ...

Answer the following (all at once):

1. What does the business want to see?
   Describe the report / dashboard / metric in plain English.
   e.g. "Daily reconciled payment totals by currency and region,
         with a count of flagged discrepancies."

2. Dimensions — what to group by?
   List fields to slice the data on.
   e.g.  reconciliation_date, currency, region

3. Metrics — what to measure?
   For each: name, aggregation, source field
   e.g.  total_amount = SUM(amount)
         payment_count = COUNT(payment_id)
         discrepancy_count = SUM(CASE WHEN is_discrepancy THEN 1 ELSE 0)

4. Time grain
   1. Daily  2. Weekly  3. Monthly  4. No aggregation (row-level)

5. Write mode
   1. Full refresh  (recommended for daily aggregates)
   2. Incremental append

6. Gold table name
   Recommended: `<catalog>.gold.<pkg_name>`  — confirm or change

7. Downstream consumers (optional — who will query this table?)
   e.g.  Tableau dashboard, downstream DAB job, data science team
   Or type "unknown"
```

### Step 5b: Present Gold design — wait for confirmation

```
GOLD DESIGN
─────────────────────────────────────────────────────────────
Input  : <catalog>.silver.<name>
Output : <catalog>.gold.<name>
Mode   : <full-refresh | incremental>

Dimensions:
  <field>  <type>

Metrics:
  <metric>  =  <aggregation>   — <business meaning>
  ...

Consumers: <listed consumers or "none registered yet">
─────────────────────────────────────────────────────────────
Confirm or correct before code is written.
```

### Step 5c: Write Gold code

After confirmation:
- `src/<pkg>/gold.py` — aggregation logic, `build_<name>(catalog, run_date)` entry point
- `notebooks/03_gold.py` — thin shim only
- `tests/test_gold.py` — unit tests: assert metric values against known input, assert row count

---

## Step 5d: Update AGENTS.md and bundle.yml with complete I/O

Now that all three tiers are defined, update the files scaffolded in Phase 2:

- **`AGENTS.md`** — replace placeholder Inputs/Outputs with real table names from Phases 3–5
- **`bundle.yml`** — replace single `run` task with three sequential tasks:
  `ingest → silver → gold` with proper `depends_on` chain

---

## Phase 6 — Register in Three Places

All three must land in the same PR as the app code.

### `pyproject.toml`
> [Phase 6] About to add workspace member to root pyproject.toml.

```diff
 [tool.uv.workspace]
 members = [
+    "apps/<name>",
 ]
```

### `CODEOWNERS`
> [Phase 6] About to add CODEOWNERS entry (skip if wildcard already covers it).

If no wildcard covers `apps/<name>`, add before `# ---- Libraries ----`:
```
/apps/<name>/   @cdo/<team>
```

### `docs/data-architecture.md`
> [Phase 6] About to regenerate data-architecture.md from AGENTS.md files.

```bash
make data-map
make check-data-map
git add docs/data-architecture.md
```

---

## Phase 7 — Claude & AI Context Setup

This phase is only needed if the human answered "yes" to Claude context
in Pre-Flight. Ask if unsure.

### Step 7a: Create app-level CLAUDE.md

> [Phase 7] About to create apps/<name>/CLAUDE.md — this gives Claude domain context when helping with future development on this app.

The app-level CLAUDE.md tells Claude what the app does, what rules must
never be broken, and which data contracts are in place. Template:

```markdown
# <name> — Claude Context

## What this app does
<Goal from Pre-Flight.>

## Domain rules (never violate these)
- <e.g. "Never modify the gold schema without a PR approved by @cdo/finance-team">
- <e.g. "Quality rules in silver.py are contractual — changing thresholds requires data governance sign-off">
- <e.g. "All outputs are classified Restricted — no PII columns may be added without PDPA review">

## Data contracts
| Table | Classification | SLA | Owner |
|---|---|---|---|
| <output-table> | <Restricted/Internal> | <99.9% by 06:00 SGT> | @cdo/<team> |

## How to run locally
```bash
make test P=apps/<name>
make lint P=apps/<name>
make bundle-validate P=apps/<name>
```

## Gotchas
- <e.g. "Partition pruning is critical — always filter by order_date first">
- <e.g. "Gold is full-refresh — do not read from it within the 2-min overwrite window">
```

### Step 7b: Prompt about domain-specific skills

Ask the human:

> "Does this app have domain-specific patterns that Claude should follow
> consistently across sessions? For example:
> - A finance reconciliation app might need a skill documenting the
>   reconciliation algorithm, tolerance thresholds, and exception rules.
> - A data quality app might need a skill listing all quality rule patterns.
>
> If yes, we can create a skill under `.claude/skills/<skill-name>/`
> now as a reference. Would you like to do that?"

If yes, help draft the skill using the `repo-health-check` or `migrate-app`
skills in this repo as structural examples.

### Step 7c: Identify applicable platform skills

Tell the human which existing platform skills apply to this app:

| Situation | Skill to reference |
|---|---|
| Migrating legacy code later | `migrate-app` |
| Platform ownership audit | `repo-health-check` |
| Finding reusable libs | `make list-libs` |

---

## Phase 8 — Write the ADR

> [Phase 8] About to create docs/adr/00NN-<name>.md — records why this app was created (required for audit trail).

```markdown
# 00NN: Create <name>

## Status
Accepted

## Context
<Why this app is being built. What business problem it solves.
What alternatives were considered.>

## Decision
Create `apps/<name>` as a Databricks Asset Bundle owned by @cdo/<team>.

## Consequences
- <Downstream consumers to be aware of new output tables.>
- <Any schema contracts or SLAs introduced.>

## Owner
@cdo/<team>
```

---

## Phase 9 — Pre-CI Checks (all must pass before opening MR)

```bash
make lint P=apps/<name>            # ruff + mypy
make test P=apps/<name>            # pytest
make test-cov P=apps/<name>        # >=80% coverage
make bundle-validate P=apps/<name> # DAB YAML valid
pre-commit run --all-files         # boundaries, agentsmd-lint, ownership-sync
make check-data-map                # architecture doc is current
make affected                      # CI scope picks up the new app
```

Fix any failure before opening an MR.

---

## CI Compliance Checklist

**Structure**
- [ ] Pre-Flight answers captured — no TODOs remain in any committed file
- [ ] Design review (Phase 1) confirmed by human before scaffold ran

**Tiers**
- [ ] Bronze design confirmed before `ingest.py` was written
- [ ] Silver design confirmed before `silver.py` was written — quality rules documented
- [ ] Gold design confirmed before `gold.py` was written — metrics and consumers documented
- [ ] `AGENTS.md` updated with final Inputs/Outputs from all three tiers (no placeholders)
- [ ] `bundle.yml` has three tasks (`ingest → silver → gold`) with `depends_on` chain
- [ ] `bundle.yml` has dev/staging/prod targets with `run_as` on staging/prod

**Quality**
- [ ] `make lint` passes
- [ ] `make test` passes — meaningful tests for each tier (not smoke tests)
- [ ] `make test-cov` passes (>=80%)
- [ ] `make bundle-validate` passes
- [ ] `pre-commit run --all-files` passes

**Registry**
- [ ] `pyproject.toml` workspace member added
- [ ] `CODEOWNERS` covers the new app
- [ ] `docs/data-architecture.md` updated and committed

**Documentation**
- [ ] ADR committed in `docs/adr/`
- [ ] App-level `CLAUDE.md` created (if human opted in)
- [ ] No hardcoded secrets — use `${secrets.scope.key}`
- [ ] MR includes change-ticket ID (SOC2 requirement)
- [ ] CODEOWNER approval not by the author

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Skipped Pre-Flight — TODOs left in AGENTS.md | Fill all stubs in Phase 2b before committing |
| Skipped Design Review — scaffold ran before approval | Always show the design table and wait for confirmation |
| Smoke test instead of meaningful unit test | Test real behaviour — assert outputs, not just "it ran" |
| Skipped Phase 0 cross-app table scan | User may not know what tables already exist — always show the list before asking about sources |
| Importing another app's Python code | Blocked by pre-commit — use `libs/` for shared code, Delta reads for shared data |
| Skipped Bronze design review — wrote code before confirming schema | Show the design table and wait; source fields change often |
| Silver quality rules not documented | Rules are contractual — write them in AGENTS.md Rules section |
| Gold metrics not confirmed before writing | Business requirements change; confirm the exact aggregations first |
| `bundle.yml` missing staging/prod `run_as` | Passes dev deploy, fails staging — add service principal |
| No CLAUDE.md for a complex domain app | Future Claude sessions lose context — create it in Phase 7 |
| Domain skill not created | Patterns get re-explained every session — write the skill once |
| ADR skipped | Required for audit trail — takes 5 minutes, blocks SOC2 gap |
| `data-architecture.md` not committed | `make check-data-map` fails in CI |
