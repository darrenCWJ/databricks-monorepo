# mono-dev — agent guide

## What this repo is
Monorepo for the data platform. Polyglot: Python (PySpark, ML),
Scala (Spark streaming).
Deploy unit: Databricks Asset Bundle (DAB), one per directory under `apps/`.

## Command surface (use these, not ad-hoc commands)
- `make setup` — install all deps, set up pre-commit
- `make test P=<path>` — run tests scoped to path (file or dir)
- `make lint P=<path>` — ruff + mypy + scalafmt
- `make bundle-validate P=<path>` — `databricks bundle validate`
- `make bundle-deploy P=<path> T=dev` — deploy bundle to dev target
- `make affected` — list bundles affected by current git diff
- `make new-app NAME=<name> KIND=python|scala|streaming` — scaffold a new DAB
- `make import-job JOB_ID=<id> T=<path>` — import an existing Databricks Job (see docs/runbooks/import-existing-job.md)

## Folder map
- `apps/`    deploy units (DABs). Edit here to ship behaviour.
- `libs/`    shared Python packages. Bump consumers when API changes.
- `infra/`   Terraform + Unity Catalog. Touch with care.
- `tools/`   cross-cutting scripts, templates.
- `docs/`    ADRs, runbooks, compliance, onboarding.

## Rules for changes
1. Never edit across `apps/` boundaries in one PR. Boundaries are owned by
   different teams (see CODEOWNERS).
2. Library API changes go in a dedicated PR; consumers update separately.
3. New deploy unit = new directory under `apps/` with `bundle.yml` + `AGENTS.md`.
4. Tests must pass locally before opening a PR (`make test P=<path>`).
5. Notebook code that isn't unit-tested must be wrapped in a thin Python
   function in `src/` that IS tested.
6. Do not commit secrets. Use Databricks secret scopes; reference via
   `${secrets.scope.key}` in `bundle.yml`.

## Agents in scope
Claude Code, Cursor, Copilot, Aider, Databricks Code Assistant / Genie Code,
internal agentic pipelines. All read AGENTS.md (some via the Git Folder
auto-index, some via explicit context paste). CI gates apply equally to
all of them; nothing about a Databricks-native agent bypasses the
governance scaffolding.

## Imports (read these when relevant)
@docs/runbooks/branching-strategy.md
@docs/runbooks/access-control.md
@docs/runbooks/databricks-git-folder-workflow.md
@docs/runbooks/databricks-code-assistant.md
@docs/runbooks/create-a-new-project.md
@docs/glossary.md
@docs/adr/
