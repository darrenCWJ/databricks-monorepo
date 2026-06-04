# output "dev_cluster_url" {
#   value = module.dev_compute.cluster_url
# }

output "group_names" {
  value = module.iam.group_names
}

output "group_ids" {
  value = module.iam.group_ids
}

output "uc_iam_role_arns" {
  description = "ARNs of the four UC/workspace cross-account IAM roles managed by this Terraform."
  value = {
    workspace  = module.s3_workspace_data_bucket.iam_role_arn
    data       = module.s3_dev_data_bucket.iam_role_arn
    landing    = module.s3_landing_data_bucket.iam_role_arn
    autoloader = module.s3_autoloader_data_bucket.iam_role_arn
  }
}

output "cross_account_role_arn" {
  description = "ARN of the pre-existing Databricks cross-account IAM role (EC2 provisioning, not managed here). 'not found' if absent."
  value       = length(data.aws_iam_roles.cross_account.arns) > 0 ? tolist(data.aws_iam_roles.cross_account.arns)[0] : "'${var.cross_account_role_name}' not found in this account"
}