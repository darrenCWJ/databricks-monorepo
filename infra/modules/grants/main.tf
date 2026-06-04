terraform {
  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.0"
    }
  }
}

resource "databricks_grants" "this" {
  for_each = var.grants

  catalog           = each.value.securable == "catalog" ? each.value.name : null
  schema            = each.value.securable == "schema" ? each.value.name : null
  table             = each.value.securable == "table" ? each.value.name : null
  external_location = each.value.securable == "external_location" ? each.value.name : null

  grant {
    principal  = each.value.principal
    privileges = each.value.privileges
  }
}
