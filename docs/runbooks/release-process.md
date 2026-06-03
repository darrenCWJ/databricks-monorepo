# Release process (release branches off main)

## Cadence
Weekly cuts, Wednesday mornings SGT. Off-cycle releases allowed for hotfixes.

## Cutting a release

1. Release manager creates `release/YYYY-MM-DD` from `main`:
   ```bash
   git checkout main && git pull
   git checkout -b release/$(date +%F)
   git push -u origin release/$(date +%F)
   ```
2. GitLab CI runs validation on the release branch.
3. Trigger `deploy-staging` job (manual). Run integration tests.
4. After 24 hours bake on staging, trigger `deploy-prod` (manual; protected
   environment requires distinct approver).
5. Tag the release: `git tag v$(date +%F) && git push --tags`

## Hotfix flow

1. Create a branch from the active `release/*`: `git checkout -b hotfix/CHG-1234 release/2026-05-15`
2. Open MR targeting the `release/*` branch.
3. After merge, cherry-pick back to `main`: `git checkout main && git cherry-pick <sha>`
4. Trigger `deploy-prod` from the release branch.

## Rollback

Re-deploy the previous `release/*` branch:
```bash
git checkout release/2026-05-08
# trigger deploy-prod manually in GitLab
```

The audit trail in S3 will show the rollback as a fresh deploy with the
older git_sha.
