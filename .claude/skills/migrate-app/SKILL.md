---
name: migrate-app
description: Use when migrating an existing standalone repo, script, or Databricks Job into the monorepo as a new app under apps/. Applies to lift-and-shift of Python or Scala workloads, notebook-heavy jobs needing DAB conversion, and any external codebase being onboarded into the CDO platform.
---

# Migrate App into Monorepo

## Overview

Converts a standalone repo or legacy script into a first-class monorepo app under `apps/`. Done when: code lives in the correct structure, `docs/data-architecture.md` reflects the app, all pre-CI gates pass, and an ADR exists.

**Not this skill:** Greenfield app with no existing code — use `docs/runbooks/create-a-new-project.md`.

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

```bash
make lint P=apps/<name>            # ruff + mypy
make test P=apps/<name>            # pytest (>=1 unit test required)
make bundle-validate P=apps/<name> # DAB YAML — no Databricks connection needed
pre-commit run --all-files         # boundaries, agentsmd-lint, ownership-sync
make check-data-map                # architecture doc is current
make affected                      # confirms CI scope picks up the new app
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

- [ ] `make lint` passes (ruff, mypy)
- [ ] `make test` passes (>=1 unit test)
- [ ] `make bundle-validate` passes
- [ ] `pre-commit run --all-files` passes
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
| Business logic in notebook | Extract to `src/<package>/job.py` — notebook is 4 lines |
| Skipped `pyproject.toml` workspace entry | App invisible to `uv sync`; add to `members` |
| Empty Inputs/Outputs in AGENTS.md | `make data-map` produces no row; fill them in first |
| `data-architecture.md` not committed | `make check-data-map` fails in CI |
| Cross-team Python import | Pre-commit blocks; move to `libs/` or read via Delta |
| No CODEOWNERS entry | `@cdo/platform-team` becomes default reviewer for everything |
| No `run_as:` in staging/prod targets | Passes dev deploy, fails staging — add service principal |
| Hardcoded catalog or schema string | Use `${var.catalog}` in `bundle.yml`, pass via notebook widget |
| ADR skipped | Required for all migrations — SOC2 audit evidence |
