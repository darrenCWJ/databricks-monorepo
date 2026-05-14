# infra/ — agent rules

> Extends the root AGENTS.md.

## Touching infra requires extra approvers

Any MR that modifies files under `infra/` automatically requires:
- `@cdo/platform-team` lead
- `@cdo/security`

## Never auto-apply Terraform

The pipeline never auto-applies. A human always triggers `terraform
apply` manually, against the right workspace, after reviewing the plan.

## Standard layout for new resources

- Workspace + catalogs → `terraform-databricks/main.tf`.
- Groups + group memberships → `terraform-databricks/groups.tf`.
- Service principals + permissions → `terraform-databricks/sps.tf`.
- Module definitions → `terraform-databricks/modules/`.
