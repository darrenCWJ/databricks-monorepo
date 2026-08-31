# CI / GitLab Workflow Rules

## Branching

- `main` — trunk, auto-deploys to dev. Never push directly. Never rebased.
- `feature/<team>-<desc>` — day-to-day work. One feature, one branch. Days, not weeks.
- `hotfix/<desc>` — branch from `main`, same flow, expedited review. No cherry-pick.
- `recovery/<tag>` — rare; from a `v/` tag, only when `main` is unshippable.

There are **no release branches**. A release is a per-project tag (`v/<project>/<date>.<n>`)
created by CI, assigned to an environment by the release manifest.

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

- Merge to `main` → CI tags the affected projects → auto-deploy to dev (no approval)
- MR bumping `release/staging/<project>.yml` → `reconcile-staging` (release approver)
- MR bumping `release/prod/<project>.yml` → `reconcile-prod` (approver != triggerer)

Promotion is per project. One project moving does not move any other.

## What NOT to Do

- Never create a `release/*` branch — promotion is a manifest MR, not a branch cut.
- Never run `databricks bundle deploy` against staging or prod by hand;
  `tools/scripts/reconcile.py` is the only thing that touches them.
- Never move or delete a `v/` tag — it is the rollback target and the audit record.
- Never let a manifest state change delete data. `retired` removes jobs, not tables.
- Never skip CI or bypass CODEOWNERS.
