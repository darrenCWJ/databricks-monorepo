# Databricks Terraform — Implementation Walkthrough

## Issues Addressed

1. Cannot create classic cluster
2. External location IAM permission not working
3. Catalog owner is wrong
4. Catalog name is wrong
5. SP naming convention

---

## 1. IAM — Moving from workspace-level to account-level

**Problem**: Users (Wei Hao, Jeffrey, Germaine) were declared in Terraform but never appeared in the workspace. They had to be added manually.

**Root cause**: `module.iam` was using the workspace-level provider (`provider "databricks" {}`). For Unity Catalog workspaces, identities must be created at the **account level** via the MWS API, then explicitly assigned to a workspace.

**Fix**:
- Added `configuration_aliases = [databricks.mws]` to the IAM module's `required_providers`
- Added `provider = databricks.mws` to every resource in the module
- Added `databricks_mws_permission_assignment` resources to assign groups/SPs to the workspace

**IAM module reorganisation**: Moved the `databricks_mws_permission_assignment` resources **inside** the IAM module (instead of root `main.tf`), and added `workspace_id` as a module input. This made the module fully self-contained: create identities → assign to workspace.

**Entitlements dead end**: `databricks_entitlements` consistently failed with "SP not found" — because it is a workspace-level resource and uses workspace-internal SCIM IDs, not account-level IDs. Fix: dropped `databricks_entitlements` entirely — `databricks_service_principal` already sets `allow_cluster_create` and `allow_instance_pool_create` at account level.

---

## 2. Catalog naming — `dev_cdo_catalog_*` → `dev_*`

**Problem**: Catalogs were named `dev_cdo_catalog_admin`, `dev_cdo_catalog_fin` etc. Required format: `{ENV}_{DOMAIN}` e.g. `dev_admin`, `dev_fin`.

**Root cause**: The `dev_catalog_storage` local key expression included `name_team` and `name_scope` segments unnecessarily.

**Fix**: Changed key from `"${v.name_env}_${v.name_team}_${v.name_scope}_${v.name_domain}"` to `"${v.name_env}_${v.name_domain}"`.

**Complication**: Existing catalogs had `force_destroy = false`. Databricks refused to destroy them even when empty because every catalog automatically gets an `information_schema`. Added `force_destroy = true` to the catalog resource in the storage module.

---

## 3. SP naming convention

**Problem**: SPs were named `dev_cdo_ms_admin`, `sp_dev_cdo_catalog_fin` etc. Authoritative naming from the Databricks Roles Confluence page: `sp_{ENV}_{TEAM}_{PURPOSE}`.

**Fix**: Renamed all SP keys and display names:
- `dev_cdo_ms_admin` → `sp_dev_cdo_metastore_admin`
- `dev_cdo_ws_admin` → `sp_dev_cdo_workspace_admin`
- `sp_dev_cdo_catalog_{domain}` → `sp_dev_cdo_catalog_admin_{domain}`

---

## 4. Catalog ownership

**Problem**: All catalogs owned by `svc-prc-1` (the Terraform-running SP). Should be owned by domain-specific catalog SPs.

**Fix**: Changed the `catalogs` variable in the storage module from `map(string)` to `map(object({ subdir, owner }))`, added an `owner` field to `databricks_catalog`, and passed each catalog's SP application ID as the owner from `main.tf`.

**Major complication — the permission chicken-and-egg**: After transferring ownership away from `svc-prc-1`, neither `svc-prc-1` nor `sp_dev_cdo_workspace_admin` could read the catalogs (no `USE CATALOG`), blocking Terraform's state refresh. Recovery steps:
- Used `sp_dev_cdo_metastore_admin` credentials (has `USE_CATALOG, MANAGE` on all catalogs) to apply catalog grants via `-target`
- Had to `terraform state rm` catalogs and external locations to break the refresh loop
- Re-imported all resources after grants were applied
- Added `sp_dev_cdo_workspace_admin` as a permanent `USE_CATALOG` grant on all catalogs so future applies don't break

**Learning**: Always grant `USE_CATALOG` to the Terraform-running SP before transferring catalog ownership — otherwise you lock yourself out.

---

## 5. External location IAM — trust policy stuck at `0000`

**Problem**: Storage credential test failed — Assume Role failing because the IAM trust policy still had `0000` as the external ID.

**Root cause**: The `null_resource.update_uc_trust_policy` uses a `local-exec` provisioner to update the trust policy after the storage credential is created. It had already run (and recorded its state), so subsequent applies didn't re-trigger it. Every full `terraform apply` resets the IAM role trust policy back to `0000` (the placeholder in the Terraform resource), then relies on the `null_resource` to fix it — but the `null_resource` only runs when its trigger (`external_id`) changes.

**Immediate fix**: `terraform taint` the `null_resource` on all three buckets to force it to re-run:
```bash
terraform taint 'module.s3_dev_data_bucket.null_resource.update_uc_trust_policy[0]'
terraform taint 'module.s3_landing_data_bucket.null_resource.update_uc_trust_policy[0]'
terraform taint 'module.s3_autoloader_data_bucket.null_resource.update_uc_trust_policy[0]'
terraform apply
```

**Permanent fix**: Added `lifecycle { ignore_changes = [assume_role_policy] }` to the `aws_iam_role.unity_catalog` resource in the storage module. This prevents Terraform from reverting the trust policy back to `0000` on every apply, since the `null_resource` owns the real policy after initial creation.

---

## 6. Permissions for GovTech Admin group

**Problem**: Jeffrey and other admins had individually hardcoded grants that got wiped during catalog/grants reconciliation. External locations had no `MANAGE` grant.

**Fix**:
- Replaced all hardcoded user principals with `module.iam.group_names["govtech_admin"]`
- Changed catalog grants from `USE_CATALOG` to `ALL_PRIVILEGES` for the group
- Added standalone `databricks_grants` resources for `MANAGE` on each external location
- Storage credential grants set to `CREATE_EXTERNAL_LOCATION` for the group

---

## 7. Removed wrong-workspace resources

**Problem**: `module.grants`, `module.bronze_schema`, `module.silver_schema`, `module.gold_schema` were referencing the `internet` catalog from a different workspace — causing refresh errors (`Catalog 'internet' is not accessible in current workspace`).

**Fix**: Removed them from `main.tf` and cleaned up orphaned state entries with `terraform state rm`.

---

## 8. Cluster policies — duplicate creation

**Problem**: After `module.dev_compute` was uncommented, Terraform tried to create cluster policies that already existed in Databricks (created when the module was previously active, then lost from state when it was commented out).

**Fix**: Used `terraform import` to bring existing policies into state using their IDs from `databricks cluster-policies list`.

---

## Key Learnings

| # | Learning |
|---|---|
| 1 | **Account level vs workspace level** — In UC workspaces, identities must be created at account level and assigned to workspaces, not created directly at workspace level |
| 2 | **`databricks_entitlements` is workspace-level only** — Uses internal workspace SCIM IDs. For UC workspaces, set SP permissions on `databricks_service_principal` directly |
| 3 | **Ownership transfer order matters** — Always grant `USE_CATALOG` to the Terraform SP before transferring catalog ownership, otherwise you lock yourself out |
| 4 | **`force_destroy = true` needed for catalogs** — Every catalog gets `information_schema` automatically, making it non-empty. Without this flag, Terraform can never destroy or recreate catalogs |
| 5 | **`null_resource` provisioners don't re-run unless triggered** — The trust policy update only fires when its trigger value changes. Use `taint` to force a re-run |
| 6 | **`lifecycle { ignore_changes }` for externally-managed attributes** — When a `local-exec` provisioner manages an attribute post-creation, add `ignore_changes` on the resource to prevent Terraform from reverting it on every apply |
| 7 | **`depends_on` on grants blocks targeted applies** — The dependency chain pulls in all related resources during refresh, making `-target` less effective than expected |
| 8 | **Group-based grants over individual user grants** — Hardcoded user principals break when ownership changes. Group grants are resilient and auto-include new members |
| 9 | **`svc-prc-1` / Terraform SP needs baseline access** — The Terraform-running SP needs `USE_CATALOG` and external location privileges to read state, even after transferring ownership to domain SPs |
| 10 | **State drift from commented-out modules** — When a module is commented out, Terraform removes resources from state but does not destroy them in the provider. Re-enabling requires `terraform import` |

---

## Current Status

| # | Issue | Status |
|---|---|---|
| 1 | Cannot create classic cluster | ⏳ Deferred — `iam:PassRole` fix identified, pending review |
| 2 | External location IAM permission not working | ✅ Fixed |
| 3 | Catalog owner is wrong | ✅ Fixed |
| 4 | Catalog name is wrong | ✅ Fixed |
| 5 | SP naming convention | ✅ Fixed |
