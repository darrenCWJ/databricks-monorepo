variable "groups" {
  description = "Map of Databricks groups to create at the account level"
  type = map(object({
    # Set display_name for an explicit name, or set the three name_* fields to
    # auto-generate grp_{name_env}_{name_team}_{purpose}
    display_name               = optional(string, "")
    name_env                   = optional(string, "")
    name_team                  = optional(string, "")
    purpose                    = optional(string, "")
    allow_cluster_create       = optional(bool, false)
    allow_instance_pool_create = optional(bool, false)
    workspace_access           = optional(bool, true)
    databricks_sql_access      = optional(bool, false)
    # true → group is assigned ADMIN on the workspace; false → USER
    is_workspace_admin = optional(bool, false)
  }))
  default = {}
}

variable "users" {
  description = "Map of Databricks users to create at the account level"
  type = map(object({
    user_name    = string
    display_name = optional(string, "")
    groups       = optional(list(string), []) # keys from var.groups
  }))
  default = {}
}

variable "service_principals" {
  description = "Map of Databricks service principals to create at the account level"
  type = map(object({
    application_id = optional(string, null)
    # Set display_name for an explicit name, or set the four name_* fields to
    # auto-generate sp_{env}_{team}_{scope}_{domain}
    display_name = optional(string, "")
    name_env     = optional(string, "")
    name_team    = optional(string, "")
    name_scope   = optional(string, "")
    name_domain  = optional(string, "")
    groups       = optional(list(string), []) # keys from var.groups
    # true → SP is assigned ADMIN on the workspace directly (in addition to group membership)
    is_workspace_admin         = optional(bool, false)
    allow_cluster_create       = optional(bool, false)
    allow_instance_pool_create = optional(bool, false)
  }))
  default = {}
}

variable "unity_catalog_grants" {
  description = "Map of Unity Catalog grants per group on a given securable object"
  type = map(object({
    group      = string       # must match a key in var.groups
    securable  = string       # e.g. "catalog", "schema"
    name       = string       # e.g. "main", "main.bronze"
    privileges = list(string) # e.g. ["USE_CATALOG", "USE_SCHEMA", "SELECT"]
  }))
  default = {}
}

variable "workspace_id" {
  description = "Databricks workspace ID used to assign account-level groups and SPs to the workspace"
  type        = number
}
