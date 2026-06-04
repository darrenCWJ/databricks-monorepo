output "workspace_id" {
  description = "Databricks workspace ID"
  value       = databricks_mws_workspaces.this.workspace_id
}

output "workspace_url" {
  description = "URL of the provisioned Databricks workspace"
  value       = databricks_mws_workspaces.this.workspace_url
}
