# infra/

Terraform that defines the Databricks workspace, catalogs, groups, and
service principals. Platform team owns this folder.

## What lives here

| Folder | What |
|---|---|
| `terraform-databricks/` | Workspace, catalogs, groups, SP grants. |
| `gitlab/server-side-hooks/` | (optional) custom GitLab server-side hooks. |

## How changes get applied

1. Edit Terraform files locally.
2. Open MR — security team must approve.
3. Merge to main triggers `terraform plan` in CI.
4. Platform team manually triggers `terraform apply` against dev workspace.
5. After dev validates, manual apply to staging/prod (different approver).

## What this folder is NOT for

- Per-app DAB config (that lives in `apps/<name>/bundle.yml`).
- Application code of any kind.
