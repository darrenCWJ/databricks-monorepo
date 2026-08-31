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

## Sandbox workaround

GPG signing fails inside the default sandbox (cannot access `~/.gnupg`).
Always run `git commit` and `git push` with `dangerouslyDisableSandbox: true`.

## Before committing

1. `make lint P=<path> && make test P=<path>` must pass
2. `code-reviewer` agent approves (no CRITICAL/HIGH issues)
3. For infra: `security-reviewer` must approve
4. If you wrote a new utility function, check `libs/` — does it belong in an existing lib?
5. If a lib was modified, run `make affected` and report the blast radius (projects, scripts, skills affected). Inform CODEOWNERS.

## Git workflow — IMPORTANT

**YOU MUST NEVER push directly to `main`.** Always use a branch + MR.

**Before creating a branch, always check first:**
```bash
git branch --show-current        # already on feature/* or hotfix/*? use it as-is
git branch -r | grep feature/    # matching remote branch? check it out and push to it
```
Only create a new branch if none fits. **Ask the user to confirm** if existing candidates are shown.

| Situation | Branch | MR target |
|-----------|--------|-----------|
| Feature / fix / chore | `feature/<team>-<desc>` | `main` |
| Prod hotfix | `hotfix/<desc>` branched off `main` | `main` |
| Promotion to stg/prod | MR editing `release/staging/` or `release/prod/` | `main` |
| Recovery (rare) | `recovery/<tag>` from a `v/` tag, only when `main` is unshippable | `main` |

### Branch naming enforcement (MANDATORY)

Before pushing ANY branch, validate the name matches one of these patterns:
- `feature/<team>-<desc>` (e.g. `feature/platform-migration-skills`)
- `hotfix/<desc>` (e.g. `hotfix/budget-null-costcentre`)
- `recovery/<tag>` (e.g. `recovery/v-finance-customer360-etl-2026-08-17.1`)

There are **no `release/*` branches**. Promotion is an MR against the release
manifest, not a branch cut. See `docs/runbooks/branching-strategy.md`.

**REJECT and ask the user to correct if the branch name:**
- Uses `feat/` instead of `feature/`
- Is missing the `<team>` prefix after `feature/`
- Uses personal names, ticket IDs only, or vague labels (e.g. `feature/fix`, `feature/john-tuesday`)

If already on a non-compliant branch, rename it before pushing:
```bash
git branch -m <old-name> feature/<team>-<desc>
```

→ Full details: `docs/runbooks/branching-strategy.md`
