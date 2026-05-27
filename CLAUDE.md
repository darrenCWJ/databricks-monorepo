# CDO Platform Monorepo — Claude Code

@AGENTS.md

## Efficiency principle

Run targeted checks for the specific action — do not scan the full repo.
Only read the AGENTS.md of the directory being edited, not every folder.

## Security pre-checks

| Action | Check first |
|--------|-------------|
| Write to a Restricted column | Verify a `mask_function` is declared on that column |
| Any change to `infra/` | Flag for security review before proceeding |

## Agent delegation

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

## Git workflow — IMPORTANT

**YOU MUST NEVER push directly to `main` or `release/*`.** Always use a branch + MR.

**Before creating a branch, always check first:**
```bash
git branch --show-current        # already on feature/* or hotfix/*? use it as-is
git branch -r | grep feature/    # matching remote branch? check it out and push to it
```
Only create a new branch if none fits. **Ask the user to confirm** if existing candidates are shown.

| Situation | Branch | MR target |
|-----------|--------|-----------|
| Feature / fix / chore | `feature/<team>-<desc>` | `main` |
| Prod hotfix | `hotfix/<ticket>` branched off active `release/*` | that `release/*` |
| Release cut | `release/YYYY-MM-DD` from `main` | n/a |

→ Full details: `docs/runbooks/branching-strategy.md`
