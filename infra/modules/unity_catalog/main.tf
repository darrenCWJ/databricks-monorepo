terraform {
  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.0"
    }
  }
}

resource "databricks_schema" "schema" {
  catalog_name = var.catalog_name
  name         = var.name
  comment      = var.comment
}