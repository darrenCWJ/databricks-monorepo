# Runbook: branching strategy

## The model

```
feature/<ticket>-<slug>    →    main    →    release/YYYY-MM-DD    →    prod
                                 │
                                 └→ auto-deploys to dev on merge
```

Three kinds of branches:

| Branch | Source | Merges to | Lives for |
|---|---|---|---|
| `feature/<ticket>-<slug>` | `main` | `main` (via MR) | Days |
| `main` | always | release branches | Forever |
| `release/YYYY-MM-DD` | `main` (cut weekly) | nothing (terminal) | 30 days |

## When to push to which

| You're doing | Branch |
|---|---|
| Building a new feature, fixing a bug | `feature/<ticket>-<slug>` |
| Reviewing or merging | MR into `main` |
| Patching prod | Hotfix MR → `main` → cherry-pick to active release |

## How to push

From local:

```bash
git checkout main && git pull
git checkout -b feature/FIN-1234-payment-recon-bugfix
# … work …
git push -u origin feature/FIN-1234-payment-recon-bugfix
# open MR via GitLab UI; CI runs; CODEOWNER approves; merge
```

From a Databricks Git folder (UI):

1. In Repos, click "Add branch", name it `feature/FIN-1234-…`.
2. Edit notebooks via UI.
3. Click "Commit & push".
4. Open MR in GitLab.

Pre-commit fires on both paths — local via Git, remote via GitLab
server-side hook.

## Releases

- **Cadence**: weekly. Release manager (rotating, named in
  `infra/terraform-databricks/groups.tf`) cuts `release/YYYY-MM-DD`
  from `main` every Monday at 09:00 SGT.
- **What's in the release**: every MR merged into `main` since the
  previous release cut.
- **What's NOT in the release**: anything still in flight on a feature
  branch.

## Hotfixes

1. Branch from `main`: `feature/HF-…`.
2. Make the minimal fix.
3. MR into `main` (still requires CODEOWNER approval, even for hotfix).
4. After merge, cherry-pick the merge commit onto the active release
   branch: `git cherry-pick -x <SHA>`.
5. Promote staging → prod manually (different approver).

## What we deliberately do NOT do

- **No long-lived feature branches.** Anything older than 14 days
  gets a re-base reminder from the platform-team bot.
- **No squash-on-merge.** Reviewers want the granularity. CI runs on
  the squashed result, so it's tested.
- **No protected `develop` branch.** `main` IS develop. The release
  branch is the production gate.

## Checklist when opening an MR

- [ ] Branch name follows the pattern
- [ ] Change-ticket ID in the MR title
- [ ] CODEOWNERS for every touched file
- [ ] CI green
- [ ] One approval, not by author

## See also

- `release-process.md` — staging → prod cadence
- `databricks-git-folder-workflow.md` — pushing from the UI
