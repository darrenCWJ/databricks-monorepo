---
name: migrate-app
description: Migrates an existing standalone repo, script, Databricks Job, or Databricks App (Streamlit, Dash, Flask, React) into the monorepo as a new app under projects/. Use when onboarding Python/Scala batch workloads, notebook-heavy jobs needing DAB conversion, or web apps onto the CDO platform.
---

# Migrate App into Monorepo

Converts a standalone repo or legacy script into a first-class monorepo app under `projects/`. Done when: code lives in the correct structure, `docs/data-architecture.md` reflects the app, all pre-CI gates pass, and an ADR exists.

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

## Pre-Flight — Resolve All 9 Items Before Proceeding (MANDATORY)

Before scanning or touching anything, every item below must be resolved. Extract answers already present in the user's message or clearly implied by context. Ask only about what remains genuinely unclear.

Present results in a single message using this format — confirmed items first, then questions:

```
Pre-Flight summary
──────────────────
✓ Domain           : finance            (from your message)
✓ Function type    : pipeline           (inferred: batch ETL)
✓ Project name     : pipeline-alert-daily (from your message)
✓ Team / owner     : @wei_hao_tan @jeffrey_siew
✓ Language         : Python             (inferred: .py files in source)
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
| 1 | **Domain** | Business domain (lowercase): `finance`, `hcm`, `infra`, etc. |
| 2 | **Function type** | `pipeline`, `streaming`, `app`, `dashboard`, `api`, `sync`, `capture` |
| 3 | **Project name** | `<function>-<subdomain>-<wildcard>` e.g. `pipeline-alert-daily` |
| 4 | **Team / owner** | `@wei_hao_tan @jeffrey_siew` (default) |
| 5 | **Language** | Python or Scala |
| 6 | **Legacy source path** | Exact path or repo URL |
| 7 | **Target catalog** | What catalog in dev/staging/prod? |
| 8 | **Schedule / trigger** | Cron expression, upstream job, or manual? |
| 9 | **Shadow run needed?** | Replacing a live prod job? If yes, Phase 7 is required. |

---

## Phase 0 — Discovery & Mapping (HUMAN REVIEW REQUIRED)

Do not scaffold until the human confirms the mapping is correct.

### Step 0: Surface available shared libraries (MANDATORY — before scanning legacy code)

> [Phase 0] About to run `make list-libs` — checking for existing libs before scanning legacy code.

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

**Why use shared libraries instead of copying legacy implementations:**
- They encode **team-validated patterns** hardened through production use
- They handle edge cases already (environment detection, OAuth token rotation, API version switching)
- They ensure **consistency** — all projects use the same session management, permissions logic, etc.
- `make affected` tracks blast radius automatically when you declare the dependency
- Re-implementing creates maintenance debt when Databricks APIs change

**During legacy scan (Step 1):** flag any code that duplicates lib functionality. Replace with lib imports during migration — do not carry over reimplementations.

**After migration:** Add to `pyproject.toml` dependencies for blast radius tracking:
```toml
dependencies = ["de-toolbox", "de-databricks"]  # only those you actually import
```

And attach the wheels in `databricks.yml` (per ADR-0006):
```yaml
artifacts:
  de_toolbox:
    type: whl
    path: ../../../libs/de_toolbox
    build: uv build --wheel

resources:
  jobs:
    <job_name>:
      tasks:
        - task_key: <task>
          libraries:
            - whl: ../../../libs/de_toolbox/dist/*.whl
```

Notebooks then import normally — **never** `sys.path.append` to a workspace path,
which couples every project to one library copy. CI fails on it.
```python
from de_toolbox.pipeline.copper import create_copper_table
```

### Step 1: Scan the legacy source

| Item | What to look for |
|---|---|
| Entry points | `if __name__ == "__main__"`, notebook cells, job scripts |
| Business logic | Functions, classes, transforms — anything not orchestration |
| Hardcoded tables | `catalog.schema.table`, `dbfs:/`, `abfss://` |
| Hardcoded secrets | API keys, passwords, tokens, connection strings |
| **External imports** | **Any `sys.path.append`, bare module import, or `from X import` that doesn't resolve to the project's own package or a pip dependency** |
| Cross-team imports | `from projects.<other_team>` or imports outside the package |
| Existing tests | `test_*.py` or `*_test.py` |
| Schedules | Cron expressions, trigger conditions, upstream dependencies |
| Config / env vars | `os.environ`, `.env` files, hardcoded environment names |

### Step 1b: Resolve external imports (BLOCKER — do not proceed until resolved)

For every unresolved import found in Step 1 — any `sys.path.append` to an
external path or bare import that doesn't resolve to a pip package:

1. **Ask the user:** "This code imports from `<module or path>` — which repo
   does this come from? Is it already in our shared libs?"

2. Present resolution options:

   | Situation | Action |
   |---|---|
   | Functionality exists in `de_toolbox` or `de_databricks` | Rewrite import to use the shared lib |
   | Code lives in another repo we own but isn't in libs yet | Flag: needs its own migration into `libs/` first (or in parallel) |
   | Code is a pip-installable package | Add to `pyproject.toml` dependencies |
   | Code is small project-specific glue | Inline into the project's `src/` |

3. **Every import must trace to:** a shared lib under `libs/<name>/src/`, the
   project's own `src/`, or a pip dependency in `pyproject.toml`. Nothing else
   is acceptable in the final state.

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
  from projects.infra_common import X    →  move to libs/ or read via Delta

Tests found
  0 test files                       →  [!!] MUST write >=1 unit test

Registry updates required
  pyproject.toml                     →  ADD workspace member
  CODEOWNERS                         →  Already covered by wildcard (* @wei_hao_tan @jeffrey_siew)
  docs/data-architecture.md          →  REGENERATE after AGENTS.md filled
─────────────────────────────────────────────────────────────────────
Proposed app name : <function>-<subdomain>-<wildcard>
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
ls projects/<domain>/ | grep <name>               # confirm name is free
make new-project DOMAIN=<domain> FUNCTION=pipeline NAME=<name> KIND=python           # or scala
```

Python only — add to root `pyproject.toml`:
```diff
 members = [
+    "projects/<domain>/<name>",
 ]
```

**For notebook-only migrations:** use a minimal pyproject.toml (name + lib dependencies only). Do NOT add to uv workspace members.

```bash
uv sync --all-packages
```

---

## Phase 2 — File Structure

Choose the layout matching your app type:

- **Databricks Job** (batch/streaming): See [file-layouts/job.md](file-layouts/job.md)
- **Databricks App** (Streamlit/Dash/Flask/React): See [file-layouts/databricks-app.md](file-layouts/databricks-app.md)

**Choosing the right structure:**
- If the legacy code is a Databricks Job with notebook tasks, migrate as notebook-only style.
- If it's a Python package or web app, migrate as src-wrapped.

**Rules applying to both types:**
- For app/api migrations: all business logic → `src/<package>/`. Entry-point files are thin shims only.
- For pipeline/streaming migrations: logic can remain in notebooks. Use notebook-only style (see ADR-0004).
- Replace hardcoded catalog/schema with `${var.catalog}` in `bundle.yml`.
- No secrets in code — use `${secrets.scope.key}` references.
- Cross-team Python imports are blocked by pre-commit → move to `libs/` or read via Delta.

---

## Phase 3 — AGENTS.md (required, ≤80 lines)

Use the template in [templates/agents-md.md](templates/agents-md.md).

**Inputs and Outputs are mandatory.** `make data-map` reads them to build the architecture catalogue. Empty sections = app invisible to the data map.

---

## Phase 3b — Schema Contract (required if project writes output tables)

Create `projects/<domain>/<name>/contracts/schema.yml` declaring all output columns:

```yaml
models:
  - name: <catalog.schema.table>
    columns:
      - name: <column>
        data_type: STRING
        meta:
          pii: false
          classification: Official-Open
          sensitivity: NA
          retention_days: 2555
```

This enables blast radius detection. Breaking changes (column removal, type changes)
will be blocked by pre-commit if downstream consumers reference these tables.

---

## Phase 4 — Register in Three Places

All three must be in the same PR as the app code.

### `pyproject.toml`
Done in Phase 1 for Python. Skip for Scala.

### `CODEOWNERS`
```bash
# CODEOWNERS uses a single wildcard (* @wei_hao_tan @jeffrey_siew) — no per-project entry needed
```
If no wildcard exists, add a line before `# ---- Libraries ----`:
```
# Not needed — wildcard covers all projects
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
make lint P=projects/<domain>/<name>
make test P=projects/<domain>/<name>
make bundle-validate P=projects/<domain>/<name>
pre-commit run --all-files
make check-data-map
make affected
```

### Additional checks

**Secrets scan:**
```bash
grep -rn "password\|api_key\|secret\|token" projects/<domain>/<name>/src/ --include="*.py"
# Every match must be a variable name or ${secrets.*} reference
```

**Hardcoded catalog scan:**
```bash
grep -rn "prod_catalog\|dev_catalog\|cdo_dev\.\|cdo_prod\." projects/<domain>/<name>/src/ --include="*.py"
# Any match = hardcoded; replace with ${var.catalog} in bundle.yml
```

**Thin shim check:**

**Skip this check for notebook-only projects** — notebooks ARE the primary code location.

```bash
# Databricks Job (src-wrapped only):
wc -l projects/<domain>/<name>/notebooks/*.py        # >20 lines = extract logic to src/

# Databricks App:
wc -l projects/<domain>/<name>/app/app.py            # >30 lines = extract logic to src/
```

**Coverage gate:**
```bash
make test-cov P=projects/<domain>/<name>             # must report >=80%
```

---

## Phase 7 — Shadow Run (only if replacing a live prod job)

```bash
make bundle-deploy P=projects/<domain>/<name> T=dev
make bundle-run P=projects/<domain>/<name> JOB=<task_key> T=dev
```

Run for ≥7 calendar days, then validate:

**Databricks Job** — compare output tables:
```bash
make diff-outputs BUNDLE=projects/<domain>/<name> \
  LEGACY=<catalog.schema.legacy_table> \
  --key <primary_key_column>
```

**Databricks App** — compare new app URL vs. legacy side-by-side. Document any behavioral differences in the MR description.

---

## CI Compliance Checklist

- [ ] All 9 Pre-Flight questions answered
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
- [ ] `AGENTS.md` has `## Runtime Dependencies` if applicable
- [ ] `contracts/schema.yml` declares all output table columns
- [ ] ADR committed in `docs/adr/`
- [ ] MR includes change-ticket ID (SOC2)
- [ ] CODEOWNER approval not by author

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Skipped Pre-Flight | Ask all 9 questions first, every time |
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
