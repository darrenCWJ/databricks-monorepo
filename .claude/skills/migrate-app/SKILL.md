---
name: migrate-app
description: Use when migrating an existing standalone repo, script, or Databricks Job into the monorepo as a new app under apps/. Applies to lift-and-shift of Python or Scala workloads, notebook-heavy jobs needing DAB conversion, and any external codebase being onboarded into the CDO platform.
---

# Migrate App into Monorepo

## Overview

Converts a standalone repo or legacy script into a first-class monorepo app under `apps/`. Done when: code lives in the correct structure, `docs/data-architecture.md` reflects the app, all pre-CI gates pass, and an ADR exists.

**Not this skill:** Greenfield app with no existing code — use `docs/runbooks/create-a-new-project.md`.

---

## Announce-Before-Act (applies to every phase)

Before taking any action — creating a file, running a command, editing a registry file — state what you are about to do and why. Use this format:

```
> [Phase X] About to <action>: <brief reason>.
> Example: "> [Phase 1] About to run `make new-app NAME=finance-payment-recon` — this creates the folder structure and stubs under apps/."
```

Then execute. Never take an action silently.

**When to announce:**
- Running any shell command
- Creating or overwriting any file
- Editing `CODEOWNERS`, `pyproject.toml`, or `docs/data-architecture.md`
- Starting or ending a phase
- Anything that changes state on disk or in the repo

**When NOT to ask for approval before acting** (announce is enough):
- Read-only scans (grep, ls, cat)
- Running checks that only produce output (lint, test, bundle-validate)

**When to STOP and wait for confirmation before acting:**
- Creating any app directory or scaffold
- Writing `AGENTS.md`, `bundle.yml`, or any source file
- Committing or pushing to git
- Deploying to any environment

---

## Pre-Flight — Clarify Before Any Action (MANDATORY FIRST STEP)

**Before scanning, scaffolding, or touching any file**, surface every uncertainty and resolve it with the human. Do not guess or assume defaults.

Ask about anything that is not explicitly stated:

| Item | Ask if not explicitly provided |
|---|---|
| **App name** | "What should the app be named? Convention is `<team>-<verb>-<noun>` (e.g. `finance-payment-recon`). Does `<suggested-name>` look right?" |
| **Team / owner** | "Which team owns this app? (e.g. `@cdo/finance-team`)" |
| **Language** | "Is this Python or Scala?" |
| **Legacy source path** | "Where is the legacy code? Please confirm the exact path or repo URL." |
| **Target catalog** | "What catalog should this write to in dev/staging/prod?" |
| **Schedule** | "What schedule should this run on, or is it triggered by another job?" |
| **Shadow run needed?** | "Does this replace a live production job? If yes, Phase 7 shadow run is required." |

**Rules:**
- Ask all unclear questions in a single message — do not drip-feed one question at a time.
- Do not proceed to Phase 0 until every item above is resolved.
- If the human's answer introduces new uncertainty, ask again before moving on.

---

## Phase 0 — Discovery & Mapping (HUMAN REVIEW REQUIRED)

Before touching any files, scan the legacy source and produce a mapping report. **Do not scaffold until the human confirms the mapping is correct.**

### Step 0: Show available shared libraries first

> [Phase 0] About to run `make list-libs` — surfacing available shared libraries before scanning legacy code so we avoid duplicating anything already in libs/.

```bash
make list-libs
```

Review the output with the human. If any lib covers functionality in the legacy source (e.g. a `finance-common` lib with validation helpers the legacy script reimplements), note it in the mapping report. The goal is to migrate business logic into `src/` **or** replace it with a lib import — not copy-paste both.

### Step 1: Scan the legacy source

Inspect the legacy repo/directory and collect:

| Item | What to look for |
|---|---|
| Entry points | `.py` files with `if __name__ == "__main__"`, notebook cells, job scripts |
| Business logic | Functions, classes, transforms — anything not orchestration |
| Hardcoded tables | Strings matching `catalog.schema.table`, `dbfs:/`, `abfss://` |
| Hardcoded secrets | API keys, passwords, tokens, connection strings in source |
| Cross-team imports | `from apps.<other_team>` or relative imports outside the package |
| Existing tests | Any `test_*.py` or `*_test.py` files |
| Schedules | Cron expressions, trigger conditions, dependencies on other jobs |
| Config / env vars | `os.environ`, `.env` files, hardcoded environment names |

### Step 2: Display PRE-STATE → POST-STATE mapping

Print this table for human review before proceeding:

```
PRE-STATE (legacy)                        POST-STATE (monorepo)
─────────────────────────────────────────────────────────────────────
Source files
  <legacy_path>/run.py               →  notebooks/run.py  [SHIM ONLY]
  <legacy_path>/utils/transform.py   →  src/<pkg>/transform.py
  <legacy_path>/config.py            →  REMOVE — values go to bundle.yml vars

Hardcoded tables (need substitution)
  prod_catalog.finance.orders        →  ${var.catalog}.bronze.orders
  prod_catalog.finance.recon_out     →  ${var.catalog}.gold.recon_daily

Secrets detected                     →  MUST rotate before deploy
  DB_PASSWORD in config.py           →  ${secrets.scope.db_password}

Cross-team imports detected
  from apps.infra_common import X    →  move to libs/ or read via Delta

Tests found
  0 test files                       →  [!!] MUST write >=1 unit test

Registry updates required
  pyproject.toml                     →  ADD workspace member
  CODEOWNERS                         →  ADD /apps/<name>/ @cdo/<team>
  docs/data-architecture.md          →  REGENERATE after AGENTS.md filled
─────────────────────────────────────────────────────────────────────
Proposed app name : <team>-<verb>-<noun>
Owner team        : @cdo/<team>
```

### Step 3: STOP — wait for human confirmation

**Do not proceed until the human explicitly confirms:**
- Proposed app name is correct
- File mappings are correct
- Table name substitutions are correct
- Secrets are acknowledged (team will rotate them)
- No unexpected cross-team imports remain

Only continue to Phase 1 after receiving explicit approval.

---

## Phase 1 — Scaffold

```bash
# Confirm name is free
ls apps/ | grep <name>

# Create the folder structure
make new-app NAME=<team>-<verb>-<noun> KIND=python   # or scala
```

Naming convention: `<team>-<verb>-<noun>` (e.g. `finance-payment-recon`).

Add the new package to root `pyproject.toml` (Python only):
```diff
 [tool.uv.workspace]
 members = [
+    "apps/<name>",
 ]
```

Then sync:
```bash
uv sync --all-packages
```

---

## Phase 2 — App File Structure

Every app must match this layout exactly:

```
apps/<team>-<verb>-<noun>/
├── AGENTS.md          # <=80 lines: purpose, I/O, SLA, owner, rules
├── bundle.yml         # DAB: jobs, clusters, schedules, targets
├── pyproject.toml     # Python deps (or build.sbt for Scala)
├── notebooks/
│   └── run.py         # Thin shim only — no business logic
├── src/<package>/
│   ├── __init__.py
│   └── job.py         # All business logic here — unit-testable
└── tests/
    └── test_job.py    # pytest, mark with @pytest.mark.unit
```

**Rules when lifting code in:**
- Business logic → `src/<package>/`. Notebooks are 4-line shims.
- Replace hardcoded catalog/schema with `${var.catalog}` in `bundle.yml`.
- No secrets in code — use `${secrets.scope.key}` references.
- Cross-team Python imports are blocked by pre-commit. Move shared code to `libs/` or read via Delta.

---

## Phase 3 — AGENTS.md (required, <=80 lines)

The scaffolded stub is incomplete. CI will block via `agentsmd-lint` until all sections are filled in.

```markdown
# <app-name>

<One paragraph: what this app does, why it exists.>

## Owner
@cdo/<team>

## Inputs
- `<catalog>.<schema>.<table>` — <what it reads and why>

## Outputs
- `<catalog>.<schema>.<table>` — <classification, SLA, what it writes>

## Schedule
<cron expression or "triggered by upstream job X">

## Rules
- No business logic in notebooks — logic lives in src/<package>/
- <any app-specific invariants, e.g. "never backfill more than 30 days">
```

**Inputs and Outputs are mandatory.** `make data-map` reads them to build the architecture catalogue. Empty sections = app invisible to the data map.

---

## Phase 4 — Register in Three Places

All three must be in the same PR as the app code.

### `pyproject.toml`
Already done in Phase 1 if Python. Skip for Scala.

### `CODEOWNERS`
Check if your team prefix already has a wildcard:
```bash
grep "/apps/<team>-" CODEOWNERS
```
If not, add a line (before `# ---- Libraries ----`):
```
/apps/<name>/   @cdo/<team>
```

### `docs/data-architecture.md`
Regenerate and commit:
```bash
make data-map         # regenerates from all AGENTS.md files
make check-data-map   # verify it matches (same check CI runs)
git add docs/data-architecture.md
```

---

## Phase 5 — Write the ADR

Required for any migration (SOC2 audit trail). Create `docs/adr/00NN-migrate-<name>.md`:

```markdown
# 00NN: Migrate <name> into Monorepo

## Status
Accepted

## Context
<Why this is being migrated. What it does. Where it lived before.>

## Decision
Migrate to `apps/<name>` as a Databricks Asset Bundle.

## Residual risks
<Schema changes, shadow-run period, downstream consumers to flip.>

## Owner
@cdo/<team>
```

---

## Phase 6 — Pre-CI Checks (run locally, must all pass)

### Automated checks
```bash
make lint P=apps/<name>            # ruff + mypy
make test P=apps/<name>            # pytest (>=1 unit test required)
make bundle-validate P=apps/<name> # DAB YAML — no Databricks connection needed
pre-commit run --all-files         # boundaries, agentsmd-lint, ownership-sync
make check-data-map                # architecture doc is current
make affected                      # confirms CI scope picks up the new app
```

### Additional validation (must be clean before MR)

**Secrets scan** — no plaintext credentials anywhere in the app:
```bash
grep -rn "password\|api_key\|secret\|token" apps/<name>/src/ --include="*.py"
# Every match must either be a variable name or a ${secrets.*} reference
```

**Hardcoded catalog/schema scan** — all table refs must use variables:
```bash
grep -rn "prod_catalog\|dev_catalog\|cdo_dev\.\|cdo_prod\." apps/<name>/src/ --include="*.py"
# Any match = hardcoded; replace with ${var.catalog} in bundle.yml
```

**Business logic in notebooks check** — notebooks must be thin shims:
```bash
wc -l apps/<name>/notebooks/*.py
# Any notebook over 20 lines is a red flag — extract logic to src/
```

**Test coverage gate:**
```bash
make test-cov P=apps/<name>
# Must report >=80% coverage across src/<package>/
```

Fix any failure before opening an MR. CI runs the same checks — fail here, not in the pipeline.

---

## Phase 7 — Shadow Run (migrations with production parity risk)

Deploy to dev alongside legacy, writing to a parallel table:
```bash
make bundle-deploy P=apps/<name> T=dev
make bundle-run P=apps/<name> JOB=<task_key> T=dev
```

Run for >=7 calendar days, then validate parity:
```bash
make diff-outputs BUNDLE=apps/<name> \
  LEGACY=<catalog.schema.legacy_table> \
  --key <primary_key_column>
```

All checks must pass or be explained in the MR.

---

## CI Compliance Checklist

MR will not pass without:

- [ ] Pre-Flight questions answered (name, team, source path, catalog, schedule confirmed)
- [ ] Phase 0 mapping reviewed and confirmed by a human
- [ ] `make lint` passes (ruff, mypy)
- [ ] `make test` passes (>=1 unit test)
- [ ] `make test-cov` passes (>=80% coverage)
- [ ] `make bundle-validate` passes
- [ ] `pre-commit run --all-files` passes
- [ ] Secrets scan clean (no plaintext credentials)
- [ ] Hardcoded catalog/schema scan clean
- [ ] No notebook over 20 lines
- [ ] `docs/data-architecture.md` updated and committed
- [ ] `CODEOWNERS` entry covers the new app directory
- [ ] `AGENTS.md` has Inputs and Outputs sections
- [ ] ADR committed in `docs/adr/`
- [ ] No secrets in source (use `${secrets.scope.key}`)
- [ ] MR includes change-ticket ID (SOC2 requirement)
- [ ] CODEOWNER approval not by the author

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Skipped Pre-Flight questions | Agent assumed the app name, team, or source path — ask first, act second |
| Skipped Phase 0 mapping review | Human must confirm the file/table mapping before any files are written |
| Business logic in notebook | Extract to `src/<package>/job.py` — notebook is 4 lines |
| Skipped `pyproject.toml` workspace entry | App invisible to `uv sync`; add to `members` |
| Empty Inputs/Outputs in AGENTS.md | `make data-map` produces no row; fill them in first |
| `data-architecture.md` not committed | `make check-data-map` fails in CI |
| Cross-team Python import | Pre-commit blocks; move to `libs/` or read via Delta |
| No CODEOWNERS entry | `@cdo/platform-team` becomes default reviewer for everything |
| No `run_as:` in staging/prod targets | Passes dev deploy, fails staging — add service principal |
| Hardcoded catalog or schema string | Use `${var.catalog}` in `bundle.yml`, pass via notebook widget |
| ADR skipped | Required for all migrations — SOC2 audit evidence |
| Secrets left in source | Rotate immediately and use `${secrets.scope.key}` references |
