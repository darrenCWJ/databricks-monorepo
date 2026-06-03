# SOC2 / SOX controls (implemented in this repo)

| Control | Implementation |
|---|---|
| Logical separation of duties | CODEOWNERS requires approval from a team other than the author; GitLab "prevent approval by author" enabled |
| Change control evidence | MR template requires change-ticket ID; CI fails without `CHG-NNNN` |
| Production deploy approval | GitLab Protected Environment `prod` — manual gate, distinct approver list |
| Immutable audit log | `tools/scripts/audit_log.py` writes every deploy to S3 bucket with Object Lock (WORM) |
| Access reviews (quarterly) | `tools/scripts/dump_access.py` exports CODEOWNERS + Databricks ACLs + UC grants for governance review |
| No prod creds on developer machines | Prod deploys via service principal only; devs read prod via UC grants, cannot write |
| Source-controlled infra | `infra/terraform-databricks/`, `infra/unity-catalog/` |
| Build reproducibility | uv lockfile + pinned pre-commit revs + pinned CI image SHAs |

## Branch model maps to SOC2 evidence

- `main` is always green and deployable to dev. Every merge writes an audit record.
- `release/YYYY-MM-DD` branches are cut from main and are the audit artefact for
  what shipped to staging/prod on that date. Re-runnable for forensics.
- Hotfix: cherry-pick to active `release/*` and back-merge to main.

## Quarterly review checklist

See `docs/runbooks/quarterly-access-review.md`.
