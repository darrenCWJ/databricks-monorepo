# Runbook: branching strategy + environment promotion

Every engineer needs to know three things on day one:
1. What branch do I create?
2. Where do I push?
3. How does my code reach prod?

This runbook answers each.

## The branches you'll touch

| Branch | Purpose | Who creates it | Lifetime |
|---|---|---|---|
| `main` | Always green, auto-deploys to **dev**. The trunk. | n/a | Permanent |
| `feature/<short-desc>` | Your day-to-day work. One feature, one branch. | You | Days to weeks |
| `release/YYYY-MM-DD` | Snapshot of `main` promoted to staging then prod. | Release manager | 6-12 months (kept as audit artefact) |
| `hotfix/<ticket>` | Emergency fix on a live release branch. | You, when prod breaks | Hours |

## How environments map to branches

| Environment | Catalog | Triggered by | Approver | Frequency |
|---|---|---|---|---|
| **dev** | `cdo_dev` | Automatic on merge to `main` | None (automatic) | Continuous |
| **staging** | `cdo_staging` | Manual trigger on a `release/*` branch | Release manager (rotating) | Weekly + ad-hoc |
| **prod** | `cdo_prod` | Manual trigger on a `release/*` branch | Distinct approver from the merger (SOC2 segregation of duties) | Weekly + ad-hoc |

The principle: **the same `release/YYYY-MM-DD` branch is promoted through staging and prod.** You don't re-build at each environment; you re-deploy the same artefact.

## Day-to-day: creating a feature branch

```bash
git checkout main
git pull
git checkout -b feature/finance-budget-fix

# ... do work, commit ...

git push -u origin feature/finance-budget-fix
```

Open an MR targeting `main`. CI runs affected-only. CODEOWNERS routes the review.

### Naming convention

Format: `feature/<team-prefix>-<short-description>`

| Good | Bad |
|---|---|
| `feature/finance-budget-fix` | `feature/fix` (no team prefix, vague) |
| `feature/supplier-spend-v2` | `feature/john-tuesday` (personal naming) |
| `feature/customer360-add-segment` | `feature/CHG-12345` (ticket as branch name; cite it in MR description instead) |

The `<team-prefix>` matches the prefix used in `apps/<team>-*` and `dbt/<team>/`. Makes branch lists scannable.

## Opening an MR

The MR template (`.gitlab/merge_request_templates/default.md`) asks for:

- **Change ticket ID** (mandatory for SOC2 — `CHG-XXXXX`)
- **What / Why / How tested** — a short description
- **Risk and rollback** — what breaks if this is wrong
- **Data classification touchpoints** — any PII / Restricted columns?
- **CODEOWNER approval** — required, not by the author

CI runs:
- `lint` (always)
- `compute-affected` → JSON manifest of impacted scopes
- `test-python`, `test-scala`, `test-dbt` (affected-only)
- `bundle-validate` for affected apps
- `security` stage: `pip-audit`, `trivy`, `ruff -S`

Expected wall time: 3-5 minutes for affected-only.

## What happens when the MR merges

```
git merge → main
   ↓
GitLab CI deploy-dev job fires
   ↓
For each affected app:
   databricks bundle deploy -t dev
   tools/scripts/audit_log.py records the deploy
   ↓
Engineer can immediately run the dev job:
   just bundle-run apps/<name> <task> -t dev
```

No human intervention. The dev environment is the sandbox; lots of merges per day are fine.

## Cutting a release (release manager only)

Weekly, Wednesday mornings SGT:

```bash
git checkout main
git pull
git checkout -b release/$(date +%F)
git push -u origin release/$(date +%F)
```

GitLab CI runs validation on the release branch. Once green, the release manager triggers `deploy-staging` in the GitLab UI (manual job).

### Promoting to prod

After 24 hours of staging bake + smoke tests pass, the release manager triggers `deploy-prod` in the GitLab UI. **GitLab Protected Environments enforce that the prod approver is NOT the same person who created the merge that introduced the change.** This is SOC2 segregation of duties.

Once prod is green: tag the release.

```bash
git tag v$(date +%F)
git push --tags
```

## Hotfixes (when prod is broken)

Branch from the active release, NOT from main:

```bash
git checkout release/2026-05-22
git checkout -b hotfix/CHG-12345
# ... fix ...
git push -u origin hotfix/CHG-12345
```

Open MR targeting the `release/*` branch, not main. Approval required. After merge:

1. Re-trigger `deploy-prod` on the release branch.
2. Cherry-pick the hotfix to `main` so it's in the next release:
   ```bash
   git checkout main
   git pull
   git cherry-pick <hotfix-sha>
   git push
   ```

This ensures the fix lives in both the current release line and on `main`.

## Rolling back

Re-deploy the previous release branch.

```bash
# In the GitLab UI: navigate to release/2026-05-15 (the previous release)
# Trigger deploy-prod
```

The audit trail in the WORM S3 bucket will show:
- The original deploy of `release/2026-05-15` (call it deploy A)
- The deploy of `release/2026-05-22` that introduced the bug (deploy B)
- The re-deploy of `release/2026-05-15` (deploy C — same git sha as A, new timestamp)

Auditors can reconstruct the timeline from these records.

## What NOT to do

- **Don't push directly to `main`.** Branch protection blocks it; if you somehow could, CODEOWNERS approval is bypassed and CI doesn't run. Use a feature branch + MR.
- **Don't push directly to a `release/*` branch.** Same reasons. Always go through an MR.
- **Don't open MRs from a release branch to main.** Releases are derived from main; never the other way round. Hotfix cherry-pick is the only flow in that direction.
- **Don't rebase a release branch.** History on `release/*` must be linear and immutable — it's audit evidence.
- **Don't delete a `release/*` branch.** Keep it for ≥ 12 months as audit evidence. GitLab supports protecting release branches from deletion.

## What if I'm pushing from a Databricks Git Folder?

Same model. The Git Folder commits and pushes to the same GitLab repo. CI runs server-side regardless of where the push originated. Pre-commit hooks don't fire from the Databricks side; rely on CI (or run `notebooks/_pre_push_check.py` first — see `docs/runbooks/databricks-git-folder-workflow.md` if it exists, otherwise pre-push validate manually in a notebook).

## The view from each role

| Role | Branches they create | Approvals they give | Releases they cut |
|---|---|---|---|
| Data engineer / analyst / scientist | `feature/<team>-*` | Within their team's neighbourhood | Never (unless designated release manager) |
| Cleared CODEOWNER | n/a | Restricted-column reviews | Never |
| Release manager (rotating) | `release/YYYY-MM-DD` | Promotions to staging | Weekly |
| Prod approver | n/a | Promotion to prod (must NOT be the merger) | Never |
| Hotfix author | `hotfix/<ticket>` | n/a | Cherry-picks back to main |

## Verifying which environment you're in (quick reference)

```bash
# Look at your DAB target
cat apps/<name>/bundle.yml | grep -A1 target

# Or via the CLI
databricks bundle summary -t dev      # or staging, prod
```

The catalog name in any SQL query (`cdo_dev`, `cdo_staging`, `cdo_prod`) tells you immediately which environment the data came from.

## See also

- `docs/runbooks/release-process.md` — full release-cutting + promotion procedure
- `docs/runbooks/bootstrap-ci-and-audit.md` — CI auth + audit bucket setup
- `docs/runbooks/codeowners-maintenance.md` — when CODEOWNERS changes
- `docs/runbooks/databricks-git-folder-workflow.md` — pushing from inside Databricks
