# mono-dev

The data platform monorepo. All pipelines, shared libraries, infrastructure,
and tooling live here as independently deployable units.

## Repository structure

```
mono-dev/
├── apps/                  # Databricks Asset Bundles — one per pipeline/job
├── libs/                  # Shared Python libraries used by 2+ apps
├── infra/                 # Terraform + Unity Catalog IaC
├── tools/                 # Cross-cutting scripts (scaffold, CI, compliance)
├── docs/                  # ADRs, runbooks, compliance, onboarding guides
├── databricks.yml         # Root DAB config (dev/staging/prod targets)
├── pyproject.toml         # Python workspace root (uv)
├── Makefile               # Command surface for all operations
├── .gitlab-ci.yml         # CI/CD pipeline (affected-only)
├── CODEOWNERS             # Per-team ownership and review routing
├── AGENTS.md              # AI agent instructions (Claude, Cursor, Copilot, Genie)
└── CLAUDE.md              # Claude Code entrypoint (imports AGENTS.md)
```

---

## Quick start

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | System or pyenv |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| make | 3.81+ | Pre-installed on macOS and Linux |
| Databricks CLI | 0.18+ | `pip install databricks-cli` or [setup-cli](https://github.com/databricks/setup-cli) |
| Git | 2.30+ | System |
| pre-commit | 3.8+ | Installed via `make setup` |

### First-time setup

```bash
git clone git@sgts.gitlab-dedicated.com:wog/gvt/dart/gvt-dsaid-dart/mono-dev.git
cd mono-dev
make setup
```

This installs all Python dependencies, sets up pre-commit hooks, and
configures the uv workspace.

### Verify everything works

```bash
make lint P=.          # Check code quality
make test P=.          # Run all tests
make affected        # See what's changed vs main
```

---

## For data engineers

You build and maintain batch/streaming pipelines that run on Databricks.

### Your workflow

1. **Create a new pipeline:**
   ```bash
   make new-app NAME=<team>-<verb>-<noun> KIND=python
   # Example: make new-app NAME=finance-payment-recon KIND=python
   ```

2. **Write your logic** in `apps/<name>/src/<package>/` (not in notebooks).

3. **Write tests first:**
   ```bash
   make test P=apps/<name>
   ```

4. **Validate the bundle:**
   ```bash
   make bundle-validate P=apps/<name>
   ```

5. **Deploy to dev:**
   ```bash
   make bundle-deploy P=apps/<name> T=dev
   ```

6. **Open a merge request** targeting `main`.

### Key conventions

- Business logic lives in `src/`, not notebooks. Notebooks are thin shims
  that call functions from `src/`.
- Each app is a Databricks Asset Bundle (DAB) with its own `bundle.yml`.
- Use `${var.catalog}` for environment-specific catalogs — never hardcode.
- Reference secrets via `${secrets.scope.key}` in `bundle.yml`.

### Relevant docs

- `docs/runbooks/create-a-new-project.md` — full project creation checklist
- `docs/runbooks/import-existing-job.md` — bring an existing Databricks Job into the repo
- `docs/runbooks/migrate-a-script.md` — convert a legacy script into a DAB
- `apps/AGENTS.md` — structure and rules for apps

---

## For data scientists

You build ML training pipelines, experiments, and model serving.

### Your workflow

1. **Prototype** in a Databricks notebook (Git Folder or local).

2. **When ready to productionise**, extract logic into a proper app:
   ```bash
   make new-app NAME=<team>-train-<model> KIND=python
   ```

3. **Structure your code:**
   ```
   apps/<name>/
   ├── src/<package>/
   │   ├── features.py      # Feature engineering
   │   ├── train.py         # Training logic
   │   └── evaluate.py      # Model evaluation
   ├── notebooks/
   │   └── run_training.py  # Thin shim calling src/
   └── tests/
       └── test_features.py # Unit tests for transforms
   ```

4. **Track experiments** using MLflow (built into Databricks).

5. **Test locally**, then open an MR:
   ```bash
   make test P=apps/<name>
   make lint P=apps/<name>
   ```

### Key conventions

- All feature engineering and transforms must be unit-testable (in `src/`).
- Notebooks should only contain widget wiring + a function call.
- Log parameters, metrics, and artifacts to MLflow.
- Data reads should use `${var.catalog}` for environment isolation.

### Working from Databricks directly

If you can't install local tools, you can work entirely from a Databricks
Git Folder. See `docs/runbooks/databricks-git-folder-workflow.md`.

---

## For platform engineers

You maintain the shared infrastructure, CI/CD, and developer tooling.

### Your responsibilities

| Area | Location |
|------|----------|
| Unity Catalog grants, masks, row filters | `infra/unity-catalog/` |
| Workspace provisioning | `infra/terraform-databricks/` |
| CI/CD pipeline | `.gitlab-ci.yml` |
| Scaffolding tools | `tools/scripts/` |
| Pre-commit hooks | `.pre-commit-config.yaml` |
| Team ownership routing | `CODEOWNERS` |
| Compliance controls | `docs/compliance/` |

### Common tasks

**Add a new team to the monorepo:**
1. Add CODEOWNERS wildcard: `/apps/<team>-*/  @cdo/<team>`
2. Document in `docs/data-architecture.md`

**Update CI pipeline:**
- Edit `.gitlab-ci.yml` (requires `@cdo/platform-team` + `@cdo/security` review)

**Modify access grants:**
- Edit `infra/unity-catalog/main.tf`
- See `docs/runbooks/access-control.md` for the four-layer model

**Run quarterly audit:**
```bash
make dump-access T=prod
```

### Relevant docs

- `docs/runbooks/access-control.md` — four-layer access model
- `docs/runbooks/bootstrap-ci-and-audit.md` — CI setup
- `docs/runbooks/codeowners-maintenance.md` — managing CODEOWNERS
- `docs/compliance/` — IM8, PDPA, SOC2 controls

---

## For AI agent operators

You configure and manage AI coding agents (Claude Code, Cursor, Copilot,
Databricks Code Assistant / Genie Code) that work in this repo.

### How agents discover context

```
AGENTS.md (root)           <- Every agent reads this first
├── apps/AGENTS.md         <- Domain guide for apps
├── apps/<name>/AGENTS.md  <- Per-project context (when projects exist)
├── libs/AGENTS.md         <- Domain guide for libraries
├── infra/AGENTS.md        <- Infrastructure rules
└── tools/AGENTS.md        <- Available scripts
```

- **Claude Code**: reads `CLAUDE.md` which imports `AGENTS.md`.
- **Cursor/Copilot**: reads `AGENTS.md` directly from repo root.
- **Databricks Code Assistant / Genie Code**: reads from Git Folder;
  may need explicit prompt to load `AGENTS.md`.

### Governance

All agents follow the same rules as human engineers:
- CI gates apply equally (lint, test, bundle-validate, security scan).
- CODEOWNERS routes review regardless of who/what authored the change.
- No "agent-approved" fast path exists. Same MR process.

### Validation prompts (test agent grounding)

After configuring a new agent, run these prompts to verify it has context:

1. "Read AGENTS.md. Tell me three rules you'll follow."
2. "Run `make affected` and tell me what would deploy."
3. "Scaffold a new Python app called `test-validation`. Show me the generated files."

### Relevant docs

- `docs/runbooks/databricks-code-assistant.md` — Genie Code setup
- `docs/runbooks/databricks-git-folder-workflow.md` — Git Folder push flow

---

## For team leads and reviewers

You review merge requests and manage team boundaries.

### How review routing works

`CODEOWNERS` defines who reviews what. Patterns are team-prefix based:

```
/apps/finance-*/    @cdo/finance-team
/apps/fraud-*/      @cdo/fraud-eng
/libs/common-*/     @cdo/platform-team
```

### Review checklist

Before approving:
- [ ] CI is green (lint + tests + bundle-validate + security)
- [ ] No cross-team boundary violations
- [ ] Business logic is in `src/`, not notebooks
- [ ] Tests exist for new functionality
- [ ] `AGENTS.md` updated if a new app/lib was created
- [ ] No hardcoded secrets or credentials
- [ ] Restricted/PII columns have appropriate masks declared

### Relevant docs

- `docs/runbooks/branching-strategy.md` — branch model and release flow
- `docs/runbooks/release-process.md` — promoting to staging/prod
- `docs/runbooks/quarterly-access-review.md` — periodic access audit

---

## Environments

| Environment | Catalog | Trigger | Purpose |
|-------------|---------|---------|---------|
| **dev** | `cdo_dev` | Auto on merge to `main` | Sandbox, fast iteration |
| **staging** | `cdo_staging` | Manual on `release/*` branch | Pre-prod validation |
| **prod** | `cdo_prod` | Manual on `release/*` branch (separate approver) | Production |

See `databricks.yml` for full target configuration.

---

## Branch model

| Branch | Purpose | Lifetime |
|--------|---------|----------|
| `main` | Trunk. Always green. Auto-deploys to dev. | Permanent |
| `feature/<team>-<desc>` | Your day-to-day work | Days to weeks |
| `release/YYYY-MM-DD` | Promoted through staging and prod | 6-12 months (audit) |
| `hotfix/<ticket>` | Emergency fix on a live release | Hours |

Full details: `docs/runbooks/branching-strategy.md`

---

## Command reference

| Command | Description |
|---------|-------------|
| `make setup` | Bootstrap: install deps + pre-commit hooks |
| `make test P=PATH` | Run pytest scoped to PATH |
| `make test-cov P=PATH` | Run tests with coverage report |
| `make lint P=PATH` | Lint (ruff + mypy) |
| `make fix P=PATH` | Auto-fix lint issues |
| `make bundle-validate P=PATH` | Validate a DAB |
| `make bundle-deploy P=PATH T=TARGET` | Deploy a DAB (default: dev) |
| `make bundle-run P=PATH JOB=JOB T=TARGET` | Trigger a job run |
| `make bundle-destroy P=PATH T=TARGET` | Tear down a DAB |
| `make new-app NAME=NAME KIND=KIND` | Scaffold new app (python/scala) |
| `make new-lib NAME=NAME` | Scaffold new shared library |
| `make import-job JOB_ID=JOB_ID T=TARGET` | Import existing Databricks Job |
| `make affected` | List what changed vs main |
| `make where-is MODEL=MODEL` | Locate a model and its consumers |
| `make dump-access T=TARGET` | Export access grants for audit |
| `make ci-local` | Run full CI locally |

---

## Further reading

| Topic | Location |
|-------|----------|
| Creating a new project | `docs/runbooks/create-a-new-project.md` |
| Branching and releases | `docs/runbooks/branching-strategy.md` |
| Access control (4 layers) | `docs/runbooks/access-control.md` |
| Working from Databricks | `docs/runbooks/databricks-git-folder-workflow.md` |
| AI agent guidance | `docs/runbooks/databricks-code-assistant.md` |
| Importing legacy jobs | `docs/runbooks/import-existing-job.md` |
| Migrating scripts | `docs/runbooks/migrate-a-script.md` |
| Compliance (IM8/PDPA/SOC2) | `docs/compliance/` |
| Architecture decisions | `docs/adr/` |
| Glossary | `docs/glossary.md` |
