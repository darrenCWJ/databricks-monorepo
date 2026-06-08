---
name: creating-projects
description: Guides the full lifecycle of a new greenfield Databricks Asset Bundle — goal clarification, lib discovery, medallion tier design (Bronze/Silver/Gold), scaffolding, registry updates, Claude context, and pre-CI gates. Use when a team needs to build a new data workflow from scratch in this monorepo with no legacy code to migrate.
---

# Creating a New Project

## Overview

Full lifecycle for a new greenfield project: clarify goal, discover reusable libs and existing tables, review design, scaffold, build tiers interactively, register in all required places, set up Claude context, write the ADR, and pass pre-CI gates.

**Not this skill:** Migrating existing code into the monorepo — use `migrate-app` instead.

---

## Announce-Before-Act (applies throughout)

Before any action, state what you are about to do and why:

```
> [Phase X] About to <action>: <brief reason>.
```

| Action type | Rule |
|---|---|
| Read-only scan | Just run — no announcement needed |
| Shell command, file write, registry edit | Announce, then execute |
| Scaffold, source files, commit | **Stop — wait for explicit confirmation** |

---

## Pre-Flight — Clarify First (MANDATORY)

Present **all questions in one message**. User replies with a number or types a custom value. Mark optional items clearly. Do not proceed until all required items (*) are resolved.

---

**Quick setup — reply with a number or type your own:**

**1. Domain*** — business domain (lowercase)
> e.g. `finance`, `hcm`, `infra`, `fraud`, `customer`

**2. Function type*** — what kind of project is this?
> 1. `pipeline` — batch ETL, orchestration, ingestion
> 2. `streaming` — real-time / continuous processing
> 3. `app` — web apps (Streamlit, Dash, Flask, React)
> 4. `dashboard` — BI dashboards / Lakeview
> 5. `api` — REST/HTTP service endpoints
> 6. `sync` — low-latency read (Lakebase sync)
> 7. `capture` — operational capture (CDC/events)

**3. Subdomain name*** — what it operates on
> e.g. `accounts-payable`, `employee-history`, `budget-viewer`
> Optional wildcard suffix for disambiguation: `-daily`, `-v2`, `-batch`
> Full project name will be: `<function>-<subdomain>`

**4. What does this project do?*** _(1–2 sentences)_
> e.g. "Reconciles daily payment transactions against bank statements and flags discrepancies."

**5. Inputs*** — tables or sources this project reads
> e.g. `cdo_dev.landing.payments` — or type "unknown" to fill in later

**6. Outputs*** — tables this project produces
> e.g. `cdo_dev.gold.payment_recon` — or type "unknown" to fill in later

**7. Schedule***
> 1. Daily at 02:00 SGT _(recommended)_
> 2. Hourly
> 3. Triggered by upstream job — type job name
> 4. On-demand only
> 5. Other — type cron expression

**8. Language***
> 1. Python _(recommended)_
> 2. Scala

**9. Business rules** _(optional — press Enter or "none" to skip)_
> e.g. "Never backfill > 30 days", "99.9% completeness SLA by 06:00 SGT"

**10. Claude context** _(optional)_
> 1. Yes — create `CLAUDE.md` _(recommended for complex domain apps)_
> 2. No

---

If any answer introduces new uncertainty, ask again before moving on.

---

## Phase 0 — Discovery (read-only)

### Step 0a: Show available shared libraries (MANDATORY — check before writing any code)

```bash
make list-libs
```

Present the libraries to the user with recommendations:

```
AVAILABLE SHARED LIBRARIES
─────────────────────────────────────────────────────────────────
Library          What it provides                                      Recommend?
de_toolbox       Medallion pipeline (copper→bronze→silver→gold),       YES if ingesting/transforming data
                 Data Vault, Kimball, DQ checks, data profiling,
                 SharePoint/Workday connectors, email notifications

de_databricks    Workspace admin: session management, IAM/SCIM,        YES if managing users, groups,
                 Unity Catalog grants, compute provisioning,           permissions, or Databricks resources
                 Tableau sync, housekeeping, catalog migration
─────────────────────────────────────────────────────────────────
```

**Why use these libraries:**
- They encode **team-validated patterns** hardened through production use
- They handle edge cases (environment detection, OAuth token rotation, API version switching)
- They ensure **consistency** across all platform projects
- Changes propagate automatically via `make affected` blast radius tracking
- Re-implementing the same logic creates maintenance debt when platform APIs evolve

**If a lib covers your need → import it.** Add to `pyproject.toml` dependencies:
```toml
dependencies = ["de-toolbox", "de-databricks"]  # only those you actually import
```

And in notebooks (per ADR-0003 src/ layout):
```python
import sys
sys.path.append("/Workspace/Repos/shared/mono-dev/libs/de_toolbox/src")
sys.path.append("/Workspace/Repos/shared/mono-dev/libs/de_databricks/src")
```

**If the user references code from an external repo not in `libs/`** — stop and ask:
"Which repo does this come from? Is it already in our shared libs, or does it
need to be migrated in?" Every import must resolve to a shared lib, a pip
dependency, or the project's own `src/`. Nothing else is acceptable.

### Step 0b: Show same-team projects for reference

```bash
ls projects/<domain>/
```

Surface similar projects so the new one can follow established patterns.

### Step 0c: Show all available output tables from other apps

Read `docs/data-architecture.md` and display:

```
AVAILABLE TABLES FROM OTHER APPS
─────────────────────────────────────────────────────────────────
App                   Owner               Outputs
<app-name>            @cdo/<team>         <catalog.schema.table>
─────────────────────────────────────────────────────────────────
Does this app need to read from any of these tables?
```

Note cross-app dependencies — they become Inputs in AGENTS.md and sources in the Bronze tier.

> Delta reads from another app's output table are fine.
> Importing another app's Python code is blocked by pre-commit — use `libs/` for shared code.

### Step 0d: Check CODEOWNERS wildcard coverage

```bash
grep "/projects/<domain>/<function>-" CODEOWNERS
```

Note whether a wildcard already covers this project's name — relevant for Phase 6.

---

## Phase 1 — Design Review (HUMAN CONFIRMS BEFORE SCAFFOLD)

Present the full design using Pre-Flight and Phase 0 findings. **Do not scaffold until explicitly approved.**

```
APP DESIGN REVIEW
─────────────────────────────────────────────────────────────────
Name         : <function>-<subdomain>-<wildcard>
Owner        : @cdo/<team>
Language     : Python | Scala
Goal         : <1-2 sentence description>

Files to create:
  projects/<domain>/<name>/AGENTS.md
  projects/<domain>/<name>/bundle.yml
  projects/<domain>/<name>/pyproject.toml
  projects/<domain>/<name>/notebooks/run.py
  projects/<domain>/<name>/src/<pkg>/job.py
  projects/<domain>/<name>/tests/test_job.py
  projects/<domain>/<name>/contracts/schema.yml

I/O:
  Reads  : <catalog.schema.table>, ...
  Writes : <catalog.schema.table>, ...
  Schedule: <cron / trigger>

Libs to import:
  <lib-name> — <why>   OR   (none)

Registry updates:
  pyproject.toml       — ADD workspace member
  CODEOWNERS           — <ADD line | already covered>
  data-architecture.md — REGENERATE after AGENTS.md filled

Claude context: <YES — create CLAUDE.md | NO>
─────────────────────────────────────────────────────────────────
Confirm the design above, or specify corrections.
```

---

## Phase 2 — Scaffold & Fill

### Step 2a: Run scaffold

> [Phase 2] About to run `make new-project DOMAIN=<domain> FUNCTION=<function> NAME=<name> KIND=python` — creates folder and stub files.

```bash
make new-project DOMAIN=<domain> FUNCTION=<function> NAME=<name> KIND=python
```

### Step 2b: Fill every stub immediately (no TODOs in committed files)

**`AGENTS.md`** — replace all TODOs with real values from Pre-Flight:
- Owner, Inputs, Outputs, Schedule, Rules

**`bundle.yml`** — set schedule, targets (dev/staging/prod), `run_as` for staging and prod.

**`src/<pkg>/job.py`** — replace hello-world stub with real entry-point:
```python
def run(catalog: str) -> None:
    """<What this does in one sentence.>
    Reads : <catalog>.schema.input_table
    Writes: <catalog>.schema.output_table
    """
```

**`tests/test_job.py`** — replace smoke test with one meaningful unit test
that asserts real behaviour (not just "it ran").

**`contracts/schema.yml`** — declare output table columns with types and classification:
```yaml
models:
  - name: <catalog.schema.table>
    columns:
      - name: <column>
        data_type: STRING|DECIMAL(18,2)|TIMESTAMP|...
        meta:
          pii: true|false
          classification: Official-Open|Official-Closed|Restricted
          sensitivity: Sensitive-Normal|Sensitive-High|NA
          retention_days: <integer>
```

This is required for all projects that write output tables. Breaking changes
(drop/rename/type-change) are blocked by pre-commit if downstream consumers exist.

---

## Phases 3–5 — Medallion Tiers

For each tier, follow this loop:
1. **Read the tier file** before asking any questions
2. Ask all design questions in one message
3. Present the design block and wait for confirmation
4. Write the code only after confirmation

**Phase 3 — Bronze / Ingest:** Load `tiers/bronze.md`

**Phase 4 — Silver / Transform:** Load `tiers/silver.md`

**Phase 5 — Gold / Serving:** Load `tiers/gold.md`

---

## Step 5d — Job Topology Review + Update AGENTS.md and bundle.yml

> [Step 5d] All tiers designed — about to show the full job DAG before writing bundle.yml.

### Show full job topology — wait for confirmation before writing bundle.yml

Using all task and table decisions from Phases 3–5, present the complete DAG:

```
JOB TOPOLOGY
─────────────────────────────────────────────────────────────────
  [<ingest_a>]           [<ingest_b>]          (parallel if split)
  bronze.<name_a>        bronze.<name_b>
        |                      |
        +──────────────────────+
                   |
            [<silver_a>]                        (waits for all ingest tasks)
            silver.<name_a>
            silver.<name_a>_quarantine
                   |
        +──────────+──────────+
        |                     |                 (parallel gold tasks if independent)
  [<gold_a>]            [<gold_b>]
  gold.<name_a>         gold.<name_b>

bundle.yml depends_on:
  <silver_a>   depends_on: [<ingest_a>, <ingest_b>]
  <gold_a>     depends_on: [<silver_a>]
  <gold_b>     depends_on: [<silver_a>]

Files per task:
  <task_name>  →  notebooks/<nn>_<task_name>.py  →  src/<pkg>/<task_name>.py
─────────────────────────────────────────────────────────────────
Confirm the job topology, or specify changes.
```

Only after confirmation:

- **`AGENTS.md`** — replace placeholder Inputs/Outputs with final table names from Phases 3–5
- **`bundle.yml`** — write all tasks with correct `depends_on`, schedule, targets, and `run_as`

---

## Phase 6 — Register in Three Places

All three must land in the same MR as the app code.

### `pyproject.toml`
> [Phase 6] About to add workspace member to root pyproject.toml.

```diff
 [tool.uv.workspace]
 members = [
+    "projects/<domain>/<name>",
 ]
```

### `CODEOWNERS`
> [Phase 6] About to add CODEOWNERS line (skip if wildcard already covers it).

If no wildcard covers `projects/<domain>/<name>`, add before `# ---- Libraries ----`:
```
/projects/<domain>/<name>/   @cdo/<team>
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

Skip if human answered "No" to Claude context in Pre-Flight.

### Step 7a: Create app-level CLAUDE.md

> [Phase 7] About to create `projects/<domain>/<name>/CLAUDE.md` — gives Claude domain context for future sessions.

Contents: what the app does, domain rules never to violate, data contracts table, how to run locally, gotchas.

### Step 7b: Ask about a domain-specific skill

Ask: "Does this app have domain patterns Claude should follow consistently across sessions? For example, a reconciliation app might need a skill documenting its tolerance thresholds and exception rules. Would you like to create one under `.claude/skills/<skill-name>/`?"

If yes, help draft it using `migrate-app` or `repo-health-check` as structural examples.

### Step 7c: Identify applicable platform skills

| Situation | Skill |
|---|---|
| Migrating legacy code later | `migrate-app` |
| Platform ownership audit | `repo-health-check` |
| Finding reusable libs | `make list-libs` |

---

## Phase 8 — Write the ADR

> [Phase 8] About to create `docs/adr/00NN-<name>.md` — required for audit trail.

```markdown
# 00NN: Create <name>

## Status
Accepted

## Context
<Why this app is being built and what problem it solves.>

## Decision
Create `projects/<domain>/<name>` as a Databricks Asset Bundle owned by @cdo/<team>.

## Consequences
- <Downstream consumers to be aware of new output tables.>
- <Any schema contracts or SLAs introduced.>

## Owner
@cdo/<team>
```

---

## Phase 9 — Pre-CI Checks

All must pass before opening an MR:

```bash
make lint P=projects/<domain>/<name>           # ruff + mypy
make test P=projects/<domain>/<name>           # pytest
make test-cov P=projects/<domain>/<name>       # >=80% coverage
make bundle-validate P=projects/<domain>/<name>
pre-commit run --all-files
make check-data-map
make affected
```

---

## CI Compliance Checklist

**Setup**
- [ ] Pre-Flight answers captured — no TODOs remain in committed files
- [ ] Design review (Phase 1) confirmed before scaffold ran

**Tiers**
- [ ] Bronze design confirmed before `ingest.py` written
- [ ] Silver design confirmed before `silver.py` written — quality rules documented
- [ ] Gold design confirmed before `gold.py` written — metrics and consumers documented
- [ ] `AGENTS.md` Inputs/Outputs match final tier definitions (no placeholders)
- [ ] `bundle.yml` has `ingest → silver → gold` with `depends_on`
- [ ] `bundle.yml` has dev/staging/prod targets with `run_as` on staging/prod

**Quality**
- [ ] `make lint` passes
- [ ] `make test` passes — meaningful tests per tier
- [ ] `make test-cov` passes (>=80%)
- [ ] `make bundle-validate` passes
- [ ] `pre-commit run --all-files` passes

**Registry**
- [ ] `pyproject.toml` workspace member added
- [ ] `CODEOWNERS` covers the new app
- [ ] `docs/data-architecture.md` updated and committed

**Documentation**
- [ ] ADR committed in `docs/adr/`
- [ ] `CLAUDE.md` created if human opted in
- [ ] No hardcoded secrets — use `${secrets.scope.key}`
- [ ] `contracts/schema.yml` declares all output columns
- [ ] `## Runtime Dependencies` filled if project calls/reads other projects
- [ ] MR includes change-ticket ID (SOC2)
- [ ] CODEOWNERS approval not by the author

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| TODOs left in AGENTS.md | Fill all stubs in Phase 2b before committing |
| Scaffold ran before design approval | Show design table and wait for confirmation |
| Smoke test instead of meaningful test | Assert real outputs, not just "it ran" |
| Phase 0 cross-app scan skipped | Always show the table list before asking about sources |
| Importing another app's Python code | Blocked by pre-commit — use `libs/` or Delta reads |
| Bronze code written before schema confirmed | Source fields change often; confirm the design first |
| Silver quality rules undocumented | Rules are contractual — write them in AGENTS.md |
| Gold metrics not confirmed | Business requirements change; confirm aggregations first |
| `bundle.yml` missing staging/prod `run_as` | Passes dev, fails staging — add service principal |
| ADR skipped | Required for SOC2 audit trail |
| `data-architecture.md` not committed | `make check-data-map` fails in CI |
