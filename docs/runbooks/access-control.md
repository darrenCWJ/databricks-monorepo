# Runbook: access control

> How access is granted, reviewed, and revoked.

## Four layers

| Layer | What | Managed in |
|---|---|---|
| **L1 — workspace** | Who can log in to Databricks. | SSO + GitLab cleared groups, SCIM-synced. |
| **L2 — Unity Catalog grants** | Who can SELECT / INSERT / USE on which catalogs and schemas. | Terraform in `infra/terraform-databricks/`. |
| **L3 — column masks** | Which columns return null / hashed values for which users. | Terraform + `libs/common-masks/`. |
| **L4 — row filters** | Which rows a user sees within a table. | Terraform + per-table `filter_by_*` functions. |

All four are code in the monorepo. No console clicks.

## Granting a new person access

HR / their manager opens a Jira ticket in `INFRA-` project:

1. Add them to the appropriate GitLab cleared group (`cdo-eng`,
   `cdo-finance-cleared`, etc.).
2. SCIM picks up the change within 15 minutes.
3. They can log in to Databricks.
4. Their reads/writes are governed by the L2/L3/L4 layers — there's no
   per-user grant.

## Granting an app access to a new table

Service principals are the only thing with write access. Granting:

1. Edit `infra/terraform-databricks/sps.tf`.
2. Add a `databricks_grant` block:

   ```hcl
   resource "databricks_grant" "finance_sp_writes_payments" {
     catalog = "cdo_prod"
     principal = databricks_service_principal.finance_sp.application_id
     privileges = ["MODIFY", "SELECT"]
     schema_name = "silver"
   }
   ```

3. MR → `@cdo/security` approves → Terraform apply by platform team.
4. The service principal now has the access. App's next run uses it.

## Granting a team access to read a Restricted column

1. Engineer's lead opens a Jira ticket explaining the business need.
2. `@cdo/data-governance` reviews the need.
3. If approved, lead opens an MR:

   - Add the lead's team's group to the mask function's allow-list in
     `libs/common-masks/cdo_core/mask_*.py`.
   - Update `docs/data-architecture.md` Table 2 if this introduces a
     new cross-team read.

4. `@cdo/restricted-cleared` approves the MR.
5. Platform team merges + applies Terraform.

## Quarterly access review

Every quarter, the platform team runs:

```bash
python tools/scripts/dump_access.py > /tmp/access-snapshot.json
```

Output: every (catalog, principal, privilege) tuple in the workspace.
Cross-checked against:

- Active employees per HR.
- Active projects per `docs/data-architecture.md` Table 1.
- CODEOWNERS rules.

Mismatches are flagged in #access-review; offboarding is run for any
principal not justified.

## Offboarding

1. HR removes the person from the GitLab cleared groups.
2. SCIM removes them from Databricks groups.
3. Their Databricks-side personal compute is auto-terminated.
4. Their MR-author history is preserved (audit trail).

## What we deliberately do NOT do

- **No personal table-level grants.** Always through a group.
- **No `ANY USER` grants.** Always through a named group.
- **No console clicks for grants.** Terraform only.
- **No "temporary" grants.** Add to Terraform with an expiry comment
  OR don't grant.

## See also

- `cleared-group-intake.md` — onboarding a new cleared team
- `codeowners-maintenance.md` — managing approver groups
- `quarterly-access-review.md` — the full review checklist
