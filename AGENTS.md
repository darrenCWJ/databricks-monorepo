# mono-dev — agent guide

## What this repo is
Monorepo for the data platform. Polyglot: Python (PySpark, ML),
Scala (Spark streaming).
Deploy unit: Databricks Asset Bundle (DAB), one per directory under `projects/`.

## Command surface (use these, not ad-hoc commands)
- `make setup` — install all deps, set up pre-commit
- `make test P=<path>` — run tests scoped to path (file or dir)
- `make lint P=<path>` — ruff + mypy + scalafmt
- `make bundle-validate P=<path>` — `databricks bundle validate`
- `make bundle-deploy P=<path> T=dev` — deploy bundle to dev target
- `make affected` — list bundles affected by current git diff (includes downstream blast radius)
- `make dep-graph` — show full dependency graph (data + lib + runtime)
- `make check-deps` — check for breaking schema changes and report downstream impact
- `make new-project DOMAIN=<domain> FUNCTION=<type> NAME=<name> KIND=python|scala` — scaffold a new project
- `make import-job JOB_ID=<id> T=<path>` — import an existing Databricks Job (see docs/runbooks/import-existing-job.md)
- `make graph` — regenerate full knowledge graph (graphify)
- `make graph-update` — incremental graph rebuild (code changes only, no LLM cost)
- `make graph-check` — validate AGENTS.md claims against knowledge graph

## Folder map
- `projects/`    deploy units (DABs), organized by domain. Edit here to ship behaviour.
- `libs/`    shared Python packages. Bump consumers when API changes.
- `infra/`   Terraform + Unity Catalog. Touch with care.
- `tools/`   cross-cutting scripts, templates.
- `docs/`    ADRs, runbooks, compliance, onboarding.

## Shared libraries (use before writing new code)

Before writing any utility function or shared logic, check `libs/` for existing
implementations. Run `make list-libs` to see what's available.

- **Always import from a shared lib** rather than duplicating logic.
- If no lib covers your need AND 2+ projects would benefit, create a new lib
  (see `libs/AGENTS.md` for the process).
- If only one project needs it, inline it in that project — promote to a lib later.
- When modifying a lib, run `make affected` to see the full blast radius
  (projects, scripts, and skills that depend on it).

See `libs/AGENTS.md` for the registry of available libraries and their exports.

## Rules for changes
1. Never edit across `projects/` boundaries in one PR. Boundaries are owned by
   different teams (see CODEOWNERS).
2. Library API changes go in a dedicated PR; consumers update separately.
3. New deploy unit = new directory under `projects/<domain>/` with `bundle.yml` + `AGENTS.md`.
4. Tests must pass locally before opening a PR (`make test P=<path>`).
5. For src-wrapped projects, notebook code must be wrapped in `src/` and tested.
   For notebook-only projects (pipelines/streaming/capture), logic can live directly in notebooks.
6. Do not commit secrets. Use Databricks secret scopes; reference via
   `${secrets.scope.key}` in `bundle.yml`.
7. **Never push directly to `main`.** All changes go through a
   `feature/<team>-<desc>` branch + MR. Hotfixes branch off `main` too — there
   are no `release/*` branches. Promotion to staging/prod is an MR editing the
   release manifest (`release/staging/`, `release/prod/`), one file per project,
   so each project promotes independently. See
   `docs/runbooks/branching-strategy.md`.

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
