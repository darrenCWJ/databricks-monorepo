---
name: migrate-app
description: Migrates an existing standalone repo, script, Databricks Job, or Databricks App (Streamlit, Dash, Flask, React) into the monorepo as a new app under apps/. Use when onboarding Python/Scala batch workloads, notebook-heavy jobs needing DAB conversion, or web apps onto the CDO platform.
---

# Migrate App into Monorepo

Converts a standalone repo or legacy script into a first-class monorepo app under `apps/`. Done when: code lives in the correct structure, `docs/data-architecture.md` reflects the app, all pre-CI gates pass, and an ADR exists.

**Not this skill:** Greenfield app with no existing code — use `docs/runbooks/create-a-new-project.md`.

---

## Announce-Before-Act

Before every state-changing action, output:
> [Phase N] About to `<action>`: `<reason>`

STOP and wait for confirmation before:
- Scaffolding or creating any files
- Editing `CODEOWNERS`, `pyproject.toml`, or `docs/data-architecture.md`
- Committing or deploying to any environment

Announce-only (no confirmation needed): read-only scans, lint/test/validate runs.

---

## Pre-Flight — Resolve All 8 Items Before Proceeding (MANDATORY)

Before scanning or touching anything, every item below must be resolved. Extract answers already present in the user's message or clearly implied by context. Ask only about what remains genuinely unclear.

Present results in a single message using this format — confirmed items first, then questions:

```
Pre-Flight summary
──────────────────
✓ App name         : fraud-alert-daily  (from your message)
✓ Team / owner     : @cdo/finance-team  (from your message)
✓ Language         : Python             (inferred: .py files in source)
✓ App type         : Databricks App — Streamlit  (from your message)
✓ Legacy path      : C:\demo-repo       (from your message)
? Target catalog   : What catalog should this write to? (cdo_dev / cdo_staging / cdo_prod)
? Schedule         : What schedule, or is it triggered by another job?
? Shadow run       : Does this replace a live production job?
```

Rules:
- Show every item — confirmed or open — in one message. Never drip-feed questions.
- Mark inferred items clearly so the user can correct them.
- Do not assume a default for any open item. Wait for explicit answers.
- If a user's answer introduces new uncertainty, ask again before proceeding.

| # | Item | Convention / hint |
|---|---|---|
| 1 | **App name** | `<team>-<verb>-<noun>` e.g. `fraud-alert-daily` |
| 2 | **Team / owner** | e.g. `@cdo/finance-team` |
| 3 | **Language** | Python or Scala |
| 4 | **App type** | Databricks Job (batch/streaming) or Databricks App (Streamlit/Dash/Flask/React)? |
| 5 | **Legacy source path** | Exact path or repo URL |
| 6 | **Target catalog** | What catalog in dev/staging/prod? |
| 7 | **Schedule / trigger** | Cron expression, upstream job, or manual? |
| 8 | **Shadow run needed?** | Replacing a live prod job? If yes, Phase 7 is required. |

---

## Phase 0 — Discovery & Mapping (HUMAN REVIEW REQUIRED)

Do not scaffold until the human confirms the mapping is correct.

### Step 0: Surface available shared libraries

> [Phase 0] About to run `make list-libs` — checking for existing libs before scanning legacy code.

```bash
make list-libs
```

Note any lib covering functionality in the legacy source. Migrate to a lib import rather than copy-pasting the implementation.

### Step 1: Scan the legacy source

| Item | What to look for |
|---|---|
| Entry points | `if __name__ == "__main__"`, notebook cells, job scripts |
| Business logic | Functions, classes, transforms — anything not orchestration |
| Hardcoded tables | `catalog.schema.table`, `dbfs:/`, `abfss://` |
| Hardcoded secrets | API keys, passwords, tokens, connection strings |
| Cross-team imports | `from apps.<other_team>` or imports outside the package |
| Existing tests | `test_*.py` or `*_test.py` |
| Schedules | Cron expressions, trigger conditions, upstream dependencies |
| Config / env vars | `os.environ`, `.env` files, hardcoded environment names |

### Step 2: Display PRE-STATE → POST-STATE mapping

```
PRE-STATE (legacy)                        POST-STATE (monorepo)
─────────────────────────────────────────────────────────────────────
Source files
  <legacy_path>/run.py               →  [see Phase 2 layout for app type]
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
App type          : Job | Databricks App (<framework>)
Owner team        : @cdo/<team>
```

### Step 3: STOP — wait for human confirmation

Do not proceed until the human confirms:
- App name and type are correct
- File mappings are correct
- Table substitutions are correct
- Secrets are acknowledged (team will rotate them)
- No unexpected cross-team imports remain

---

## Phase 1 — Scaffold

```bash
ls apps/ | grep <name>                         # confirm name is free
make new-app NAME=<name> KIND=python           # or scala
```

Python only — add to root `pyproject.toml`:
```diff
 members = [
+    "apps/<name>",
 ]
```

```bash
uv sync --all-packages
```

---

## Phase 2 — File Structure

Choose the layout matching your app type:

- **Databricks Job** (batch/streaming): See [file-layouts/job.md](file-layouts/job.md)
- **Databricks App** (Streamlit/Dash/Flask/React): See [file-layouts/databricks-app.md](file-layouts/databricks-app.md)

**Rules applying to both types:**
- All business logic → `src/<package>/`. Entry-point files are thin shims only.
- Replace hardcoded catalog/schema with `${var.catalog}` in `bundle.yml`.
- No secrets in code — use `${secrets.scope.key}` references.
- Cross-team Python imports are blocked by pre-commit → move to `libs/` or read via Delta.

---

## Phase 3 — AGENTS.md (required, ≤80 lines)

Use the template in [templates/agents-md.md](templates/agents-md.md).

**Inputs and Outputs are mandatory.** `make data-map` reads them to build the architecture catalogue. Empty sections = app invisible to the data map.

---

## Phase 4 — Register in Three Places

All three must be in the same PR as the app code.

### `pyproject.toml`
Done in Phase 1 for Python. Skip for Scala.

### `CODEOWNERS`
```bash
grep "/apps/<team>-" CODEOWNERS
```
If no wildcard exists, add a line before `# ---- Libraries ----`:
```
/apps/<name>/   @cdo/<team>
```

### `docs/data-architecture.md`
```bash
make data-map
make check-data-map
git add docs/data-architecture.md
```

---

## Phase 5 — Write the ADR

Use the template in [templates/adr.md](templates/adr.md). Required for all migrations — SOC2 audit evidence.

---

## Phase 6 — Pre-CI Checks (feedback loop: fix and re-run each failure)

After each failed check: fix the specific issue, re-run that check alone, confirm it passes before moving on. If the same check fails twice, STOP and surface the blocker to the human.

### Automated checks
```bash
make lint P=apps/<name>
make test P=apps/<name>
make bundle-validate P=apps/<name>
pre-commit run --all-files
make check-data-map
make affected
```

### Additional checks

**Secrets scan:**
```bash
grep -rn "password\|api_key\|secret\|token" apps/<name>/src/ --include="*.py"
# Every match must be a variable name or ${secrets.*} reference
```

**Hardcoded catalog scan:**
```bash
grep -rn "prod_catalog\|dev_catalog\|cdo_dev\.\|cdo_prod\." apps/<name>/src/ --include="*.py"
# Any match = hardcoded; replace with ${var.catalog} in bundle.yml
```

**Thin shim check:**
```bash
# Databricks Job:
wc -l apps/<name>/notebooks/*.py        # >20 lines = extract logic to src/

# Databricks App:
wc -l apps/<name>/app/app.py            # >30 lines = extract logic to src/
```

**Coverage gate:**
```bash
make test-cov P=apps/<name>             # must report >=80%
```

---

## Phase 7 — Shadow Run (only if replacing a live prod job)

```bash
make bundle-deploy P=apps/<name> T=dev
make bundle-run P=apps/<name> JOB=<task_key> T=dev
```

Run for ≥7 calendar days, then validate:

**Databricks Job** — compare output tables:
```bash
make diff-outputs BUNDLE=apps/<name> \
  LEGACY=<catalog.schema.legacy_table> \
  --key <primary_key_column>
```

**Databricks App** — compare new app URL vs. legacy side-by-side. Document any behavioral differences in the MR description.

---

## CI Compliance Checklist

- [ ] All 8 Pre-Flight questions answered
- [ ] Phase 0 mapping confirmed by human
- [ ] `make lint` passes
- [ ] `make test` passes (≥1 unit test)
- [ ] `make test-cov` passes (≥80%)
- [ ] `make bundle-validate` passes
- [ ] `pre-commit run --all-files` passes
- [ ] Secrets scan clean
- [ ] Hardcoded catalog scan clean
- [ ] Thin shim check passes
- [ ] `docs/data-architecture.md` updated and committed
- [ ] `CODEOWNERS` entry covers new app directory
- [ ] `AGENTS.md` has Inputs and Outputs filled
- [ ] ADR committed in `docs/adr/`
- [ ] MR includes change-ticket ID (SOC2)
- [ ] CODEOWNER approval not by author

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Skipped Pre-Flight | Ask all 8 questions first, every time |
| Skipped Phase 0 mapping review | Human must confirm before any files are written |
| Wrong layout for app type | Job uses `notebooks/`; Databricks App uses `app/` |
| Business logic in shim | Extract to `src/<package>/` |
| Skipped `pyproject.toml` workspace entry | App invisible to `uv sync` |
| Empty Inputs/Outputs in AGENTS.md | `make data-map` produces no row |
| `data-architecture.md` not committed | `make check-data-map` fails in CI |
| Cross-team Python import | Pre-commit blocks; move to `libs/` or read via Delta |
| No CODEOWNERS entry | `@cdo/platform-team` becomes default reviewer for everything |
| No `run_as:` for staging/prod | Passes dev deploy, fails staging |
| Hardcoded catalog string | Use `${var.catalog}` in `bundle.yml` |
| ADR skipped | Required for all migrations — SOC2 evidence |
| Secrets left in source | Rotate immediately; use `${secrets.scope.key}` |
