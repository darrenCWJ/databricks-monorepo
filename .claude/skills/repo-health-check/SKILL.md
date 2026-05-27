---
name: repo-health-check
description: Use when a manager or engineer asks for a platform overview, ownership audit, missing registrations, stale CODEOWNERS entries, or whether all apps/libs are properly tracked. Also use before quarterly reviews or when onboarding a new team to verify repo hygiene.
---

# Repo Health Check

## Overview

Cross-references three sources of truth and surfaces gaps in a single report:
1. **Disk** — what folders actually exist under `apps/`, `libs/`, `dbt/`
2. **CODEOWNERS** — what folders have an owner assigned
3. **`docs/data-architecture.md`** — what apps are registered in the catalogue

## Run It

```bash
make platform-health          # human-readable table
uv run python tools/scripts/check_platform_health.py --json   # machine-readable
```

## What the Report Shows

For every folder under `apps/`, `libs/`, `dbt/` it checks four columns:

| Column | Green (✅) means... | Red (❌) means... |
|---|---|---|
| **Disk** | folder exists | entry is referenced but folder is missing |
| **CODEOWNERS** | folder is covered by a rule | no owner assigned — platform-team owns everything by default |
| **Data-Arch** | app appears in `docs/data-architecture.md` | app is invisible to the data map |
| **AGENTS.md** | `AGENTS.md` file present | no metadata — tooling and agents are blind to this app |

It also flags:
- **Stale CODEOWNERS entries** — specific rules pointing to folders that don't exist on disk
- **Stale data-architecture rows** — catalogue entries for folders that don't exist

## Reading the Output

```
══════════════════════════════════════════════════════════════
  Platform Health Report — 2024-01-15
══════════════════════════════════════════════════════════════

  APPS/
  ─────────────────────────────────────────
  Folder                           Disk  CODEOWNERS  Data-Arch  AGENTS.md
  ─────────────────────────────────────────────────────────────
  demo-ingest-medallion            ✅       ✅          ✅         ✅

  LIBS/
  (no folders)

  CODEOWNERS — specific entries pointing to missing folders:
  ❌  /libs/finance-common/
  ❌  /libs/supplier-common/

══════════════════════════════════════════════════════════════
  Folders tracked : 1
  Issues          : 0
  Stale entries   : 2
  Status          : NEEDS ATTENTION
══════════════════════════════════════════════════════════════
```

**Status meanings:**
- `PASS` — every tracked folder is consistent across all three sources
- `NEEDS ATTENTION` — at least one gap or stale entry

## How to Fix Common Issues

| Issue | Fix |
|---|---|
| App on disk, missing from data-arch | Fill in `AGENTS.md` Inputs/Outputs, run `make data-map` |
| App on disk, no CODEOWNERS coverage | Add `/apps/<name>/   @cdo/<team>` to CODEOWNERS |
| App on disk, no `AGENTS.md` | Create `AGENTS.md` with Owner, Inputs, Outputs, Schedule, Rules |
| Stale CODEOWNERS specific entry | Remove the line (or create the folder if it should exist) |
| Stale data-architecture row | Run `make data-map` to regenerate from current AGENTS.md files |

## Integrating into CI

Add to `.gitlab-ci.yml` to block MRs with broken hygiene:

```yaml
platform-health:
  stage: lint
  script:
    - uv run python tools/scripts/check_platform_health.py
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

## Manager Workflow

To get a quick ownership summary before a team review:
1. `make platform-health` — get the current state
2. Share the output with team leads
3. Each ❌ in CODEOWNERS = an unowned folder — assign a team
4. Each ❌ in Data-Arch = an invisible pipeline — ask the team to update their `AGENTS.md`
5. Re-run after fixes to confirm clean state
