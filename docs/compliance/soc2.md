# SOC2 / SOX controls (implemented in this repo)

| Control | Implementation |
|---|---|
| Logical separation of duties | CODEOWNERS requires approval from a team other than the author; GitLab "prevent approval by author" enabled |
| Change control evidence | MR template requires change-ticket ID; CI fails without `CHG-NNNN` |
| Production deploy approval | GitLab Protected Environment `prod` — manual gate, distinct approver list |
| Immutable audit log | `tools/scripts/audit_log.py` writes every deploy to S3 bucket with Object Lock (WORM) |
| Access reviews (quarterly) | `tools/scripts/dump_access.py` exports CODEOWNERS + Databricks ACLs + UC grants for governance review |
| No prod creds on developer machines | Prod deploys via service principal only; devs read prod via UC grants, cannot write |
| Source-controlled infra | `infra/`, `infra/modules/unity_catalog/` |
| Build reproducibility | uv lockfile + pinned pre-commit revs + pinned CI image SHAs |

## Branch model maps to SOC2 evidence

- `main` is always green and deployable to dev. Every merge writes an audit record.
- Immutable per-project tags (`v/<project>/<date>.<n>`) are created by CI and are
  the artefact for what shipped. A tag is never moved or deleted.
- The release manifest (`release/prod/`) records which tag is live in each
  environment. `git log -p release/prod/` is a complete, timestamped,
  approver-attributed history of every production change — stronger evidence than
  a branch, which only shows what *could* have shipped.
- Hotfix: fix on `main`, CI tags it, bump the manifest. No cherry-pick.

## Quarterly review checklist

See `docs/runbooks/quarterly-access-review.md`.
