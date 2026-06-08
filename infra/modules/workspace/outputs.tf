output "workspace_id" {
  description = "Databricks workspace ID"
  value       = databricks_mws_workspaces.this.workspace_id
}

output "workspace_url" {
  description = "URL of the provisioned Databricks workspace"
  value       = databricks_mws_workspaces.this.workspace_url
}

output "root_bucket_name" {
  description = "Name of the DBFS root S3 bucket created for this workspace"
  value       = aws_s3_bucket.root.bucket
}
