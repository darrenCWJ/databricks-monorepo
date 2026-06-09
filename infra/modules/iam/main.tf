terraform {
  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.0"
      # databricks.mws  → account-level API (groups, users, SPs, workspace assignments)
      # databricks      → workspace-level API (entitlements)
      configuration_aliases = [databricks.mws]
    }
  }
}

# ── GROUPS (account level) ────────────────────────────────────────────────────
resource "databricks_group" "groups" {
  for_each = var.groups
  provider = databricks.mws

  display_name               = each.value.display_name
  allow_cluster_create       = each.value.allow_cluster_create
  allow_instance_pool_create = each.value.allow_instance_pool_create
  workspace_access           = each.value.workspace_access
  databricks_sql_access      = each.value.databricks_sql_access
}

# ── USERS (account level) ─────────────────────────────────────────────────────
resource "databricks_user" "users" {
  for_each = var.users
  provider = databricks.mws

  user_name    = each.value.user_name
  display_name = each.value.display_name
}

# Flatten user → group memberships into a single map for for_each
locals {
  user_group_memberships = merge([
    for user_key, user in var.users : {
      for group_key in user.groups :
      "${user_key}__${group_key}" => {
        user_key  = user_key
        group_key = group_key
      }
    }
  ]...)
}

resource "databricks_group_member" "user_memberships" {
  for_each = local.user_group_memberships
  provider = databricks.mws

  group_id  = databricks_group.groups[each.value.group_key].id
  member_id = databricks_user.users[each.value.user_key].id
}

# ── SERVICE PRINCIPALS (account level) ────────────────────────────────────────
locals {
  sp_display_names = {
    for key, sp in var.service_principals :
    key => sp.display_name != "" ? sp.display_name : "sp_${sp.name_env}_${sp.name_team}_${sp.name_scope}_${sp.name_domain}"
  }
}

resource "databricks_service_principal" "sps" {
  for_each = var.service_principals
  provider = databricks.mws

  application_id             = each.value.application_id
  display_name               = local.sp_display_names[each.key]
  allow_cluster_create       = each.value.allow_cluster_create
  allow_instance_pool_create = each.value.allow_instance_pool_create
}

# Flatten SP → group memberships into a single map for for_each
locals {
  sp_group_memberships = merge([
    for sp_key, sp in var.service_principals : {
      for group_key in sp.groups :
      "${sp_key}__${group_key}" => {
        sp_key    = sp_key
        group_key = group_key
      }
    }
  ]...)
}

resource "databricks_group_member" "sp_memberships" {
  for_each = local.sp_group_memberships
  provider = databricks.mws

  group_id  = databricks_group.groups[each.value.group_key].id
  member_id = databricks_service_principal.sps[each.value.sp_key].id
}

# ── WORKSPACE ASSIGNMENTS (account level) ─────────────────────────────────────
# Assigns account-level identities to the workspace with the appropriate role.
# Groups: is_workspace_admin = true → ADMIN, false → USER
# SPs:    is_workspace_admin = true → direct ADMIN assignment (e.g. CI/CD automation SP)

locals {
  workspace_group_assignments = {
    for k, g in var.groups :
    k => g.is_workspace_admin ? "ADMIN" : "USER"
  }
}

resource "databricks_mws_permission_assignment" "groups" {
  for_each = local.workspace_group_assignments
  provider = databricks.mws

  workspace_id = var.workspace_id
  principal_id = databricks_group.groups[each.key].id
  permissions  = [each.value]
}

resource "databricks_mws_permission_assignment" "ws_admin_sps" {
  for_each = { for k, sp in var.service_principals : k => sp if sp.is_workspace_admin }
  provider = databricks.mws

  workspace_id = var.workspace_id
  principal_id = databricks_service_principal.sps[each.key].id
  permissions  = ["ADMIN"]
}

