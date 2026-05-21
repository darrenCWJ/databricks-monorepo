# CDO Platform Monorepo — Claude Code

@AGENTS.md

## Efficiency Principle

Run targeted checks for the specific action — do not scan the full repo.
Only read the AGENTS.md of the directory being edited, not every folder.

## Pre-checks (scoped to the action)

| Action | Check first |
|--------|-------------|
| New app/pipeline | `ls apps/ \| grep <name>` (name collision only) |
| Edit existing app | Read that app's `AGENTS.md` for inputs/outputs/rules |
| Write to a table | Verify `mask_function` if column is Restricted |
| Change a library in `libs/` | grep consumers: `grep -r "<lib_name>" apps/*/pyproject.toml` |
| Change infra/ | Flag for security review |
| Need data from another team | Use cross-project ref (`{{ ref('project', 'model') }}`) or read via Delta — never import their Python code directly |

## Shared code (`libs/`)

- Shared libraries live in `libs/`. Apps declare dependencies in their `pyproject.toml`.
- **Editing a lib:** grep for which apps import it. If you change the API, note which consumers break.
- **Using a lib:** import it directly. If nothing in `libs/` fits, inline it — promote to a lib later if 2+ apps need it.
- CI pre-commit hook (`check_boundaries.py`) blocks cross-team Python imports. Use `libs/` or read via data contract.

## Cross-team data

- Each app's `AGENTS.md` lists its inputs (tables it reads) and outputs (tables it writes).
- To read another team's table: query it via Delta/SQL — no Python import needed.
- dbt cross-project refs: `{{ ref('platform_core', 'fct_orders') }}` — makes the dependency explicit.
- The agent does NOT need to scan other apps to find available tables. Check `docs/data-architecture.md` Table 2 if unsure what's available.

## Agent delegation (action-dependent)

| Action | Agent | Why |
|--------|-------|-----|
| New feature with multiple dependencies | `planner` | Identify cross-app dependencies upfront |
| Writing new code | `tdd-guide` | Tests alongside implementation |
| Security-sensitive code (auth, grants, PII, masks) | `security-reviewer` | Block commit until resolved |
| Build/lint fails | `build-error-resolver` | Fix immediately |
| Code written and ready for commit | `code-reviewer` | Quality gate before merge |
| Terraform / Unity Catalog changes | `security-reviewer` + `architect` | Both required |

Skip agents for simple tasks (single-file edits, running commands, docs updates).

## Before committing

1. `make lint P=<path> && make test P=<path>` must pass
2. `code-reviewer` agent approves (no CRITICAL/HIGH issues)
3. For infra: `security-reviewer` must approve
