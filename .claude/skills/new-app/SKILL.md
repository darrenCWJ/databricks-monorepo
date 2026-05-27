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

### Step 0c: Check CODEOWNERS for existing team wildcard

```bash
grep "/apps/<team>-" CODEOWNERS
```

If a wildcard already covers the new app's name, no new CODEOWNERS line is
needed. Note the result for Phase 3.

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

## Phase 3 — Register in Three Places

All three must land in the same PR as the app code.

### `pyproject.toml`
> [Phase 3] About to add workspace member to root pyproject.toml.

```diff
 [tool.uv.workspace]
 members = [
+    "apps/<name>",
 ]
```

### `CODEOWNERS`
> [Phase 3] About to add CODEOWNERS entry (skip if wildcard already covers it).

If no wildcard covers `apps/<name>`, add before `# ---- Libraries ----`:
```
/apps/<name>/   @cdo/<team>
```

### `docs/data-architecture.md`
> [Phase 3] About to regenerate data-architecture.md from AGENTS.md files.

```bash
make data-map
make check-data-map
git add docs/data-architecture.md
```

---

## Phase 4 — Claude & AI Context Setup

This phase is only needed if the human answered "yes" to Claude context
in Pre-Flight. Ask if unsure.

### Step 4a: Create app-level CLAUDE.md

> [Phase 4] About to create apps/<name>/CLAUDE.md — this gives Claude domain context when helping with future development on this app.

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

### Step 4b: Prompt about domain-specific skills

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

### Step 4c: Identify applicable platform skills

Tell the human which existing platform skills apply to this app:

| Situation | Skill to reference |
|---|---|
| Migrating legacy code later | `migrate-app` |
| Platform ownership audit | `repo-health-check` |
| Finding reusable libs | `make list-libs` |

---

## Phase 5 — Write the ADR

> [Phase 5] About to create docs/adr/00NN-<name>.md — records why this app was created (required for audit trail).

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

## Phase 6 — Pre-CI Checks (all must pass before opening MR)

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

- [ ] Pre-Flight answers captured — no TODOs remain in any committed file
- [ ] Design review confirmed by human before scaffold ran
- [ ] `make lint` passes
- [ ] `make test` passes (>=1 meaningful unit test — not just a smoke test)
- [ ] `make test-cov` passes (>=80%)
- [ ] `make bundle-validate` passes
- [ ] `pre-commit run --all-files` passes
- [ ] `AGENTS.md` has Inputs, Outputs, Schedule, Rules — no TODOs
- [ ] `bundle.yml` has dev/staging/prod targets with `run_as` on staging/prod
- [ ] `pyproject.toml` workspace member added
- [ ] `CODEOWNERS` covers the new app
- [ ] `docs/data-architecture.md` updated and committed
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
| `bundle.yml` missing staging/prod `run_as` | Passes dev deploy, fails staging — add service principal |
| No CLAUDE.md for a complex domain app | Future Claude sessions lose context — create it in Phase 4 |
| Domain skill not created | Patterns get re-explained every session — write the skill once |
| ADR skipped | Required for audit trail — takes 5 minutes, blocks SOC2 gap |
| `data-architecture.md` not committed | `make check-data-map` fails in CI |
