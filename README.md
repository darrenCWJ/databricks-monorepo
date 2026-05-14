# CDO Data Platform

The shared codebase for every data pipeline at CDO. One repository, one set of
rules, one way of working.

## What lives here

| Folder | What goes inside |
|---|---|
| `apps/` | Data pipelines and services. One folder per project. |
| `libs/` | Shared code reused by 2+ apps. |
| `infra/` | Terraform + Databricks workspace configuration. |
| `docs/` | Architecture, runbooks, ADRs, compliance docs. |
| `tools/` | Helper scripts that operate on this repo (audit log, scaffolds, checks). |

## Compulsory files at the root

| File | Why it exists |
|---|---|
| `AGENTS.md` | The rulebook AI agents and humans both read. |
| `CODEOWNERS` | Who approves what. |
| `databricks.yml` | Asset Bundle root for the whole repo. |
| `pyproject.toml` | uv workspace declaration. |
| `.pre-commit-config.yaml` | Quality gates that fire before every commit. |
| `.gitlab-ci.yml` | CI pipeline. |
| `justfile` | Local task runner — every common command. |
| `.gitignore`, `.editorconfig` | Standard housekeeping. |

## First time setup

```bash
just setup        # install Python deps + pre-commit hooks
just lint         # run all linters
just test         # run all tests
```

## Adding a new project

See `docs/runbooks/create-a-new-project.md`. Half a day end-to-end.

## Help

- Architecture: `docs/data-architecture.md`
- How-tos: `docs/runbooks/`
- Compliance: `docs/compliance/`
