# Runbook: release process

> Promoting code from `main` to staging, then prod.

## Cadence

- **Release branch cut**: every Monday 09:00 SGT.
- **Staging deploy**: triggered manually right after the cut, by the
  release manager.
- **Prod deploy**: ≥ 24 hours after staging, manually triggered by a
  **different person** than the release manager (SOC2 segregation of
  duties).

## Cutting a release

Release manager runs:

```bash
git checkout main && git pull
git checkout -b release/$(date +%Y-%m-%d)
git push -u origin release/$(date +%Y-%m-%d)
```

Or via the GitLab UI: Repository → Branches → New branch from `main`.

## Deploying to staging

In GitLab CI:

1. Go to the release branch's pipeline.
2. Manual job `deploy-staging` → click "Play".
3. CI runs `databricks bundle deploy -t staging` and writes a record
   to `system.audit.deploy_events`.
4. Bake on staging for ≥ 24 hours.
5. Run smoke tests against staging:

   ```bash
   just smoke-test apps/<name> -t staging
   ```

## Deploying to prod

**Distinct-approver rule**: the person clicking "Play" on `deploy-prod`
MUST NOT be the one who merged the last MR in the release. CI enforces
this by checking the merge commit author against the pipeline trigger
actor.

1. In GitLab CI, find the release branch's pipeline.
2. Manual job `deploy-prod` → "Play".
3. CI runs `databricks bundle deploy -t prod` + audit log write.
4. Monitor PagerDuty + #incidents for the first 30 minutes.

## Rollback

When prod deploy goes wrong:

1. **Same release branch, previous commit**:

   ```bash
   databricks bundle deploy -t prod \\
     --git-commit $(git rev-parse HEAD~1)
   ```

   The DAB metadata catalog tracks every deployed bundle version, so
   Databricks itself is rolled back.

2. **Data damage** (wrong rows written): restore from time travel:

   ```sql
   INSERT OVERWRITE TABLE cdo_prod.silver.payments
   SELECT * FROM cdo_prod.silver.payments
   TIMESTAMP AS OF '<5 minutes before bad deploy>'
   ```

3. **Always write an incident report** under `docs/adr/00NN-incident-…md`.

## What gets deployed

The release branch IS the deploy artefact. Whatever lives on it at the
moment `bundle deploy` runs gets deployed. So:

- **Don't commit to a release branch directly** unless it's a hotfix
  cherry-pick.
- **Don't reuse a release branch** for a later release. Cut a new one.

## Audit trail

Every deploy writes to:

- `system.audit.deploy_events` — Databricks system table, queryable.
- `cdo-soc2-audit` S3 bucket — WORM, 7-year retention.

Auditors get a read-only role against both.

## Checklist (for the release manager)

- [ ] Release branch cut from green `main`
- [ ] Staging deployed
- [ ] Smoke tests passed on staging
- [ ] ≥ 24h bake on staging
- [ ] Different approver clicked Play on prod
- [ ] First 30 minutes of prod monitored
- [ ] Release notes posted to #data-platform

## See also

- `branching-strategy.md` — how the release branch is born
- `access-control.md` — who can click which deploy buttons
