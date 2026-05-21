# CI / GitLab Workflow Rules

## Branching

- `main` — trunk, auto-deploys to dev. Never push directly.
- `feature/<team>-<desc>` — day-to-day work. One feature, one branch.
- `release/YYYY-MM-DD` — cut weekly by release manager. Never rebase.
- `hotfix/<ticket>` — branch from release, cherry-pick back to main.

## Merge Requests

- Always include change ticket ID (SOC2 requirement).
- MR must pass: lint, compute-affected, tests (affected-only), bundle-validate, security.
- CODEOWNER approval required (not by the author).
- Restricted column changes require `@cdo/data-governance` + `@cdo/restricted-cleared`.

## CI Pipeline Stages

1. `lint` — always runs (ruff, mypy, scalafmt, sqlfluff)
2. `compute-affected` — JSON manifest of impacted scopes
3. `test-python` / `test-scala` / `test-dbt` — affected-only
4. `bundle-validate` — DAB syntax for affected apps
5. `security` — pip-audit, trivy, ruff -S

## Deploy Flow

- Merge to `main` → auto-deploy to dev (no approval)
- `release/*` → manual trigger to staging (release manager)
- `release/*` → manual trigger to prod (different approver than merger)

## What NOT to Do

- Never open MRs from release to main (only cherry-pick hotfixes).
- Never delete release branches (audit evidence, keep 12+ months).
- Never skip CI or bypass CODEOWNERS.
