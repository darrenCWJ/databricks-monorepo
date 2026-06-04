variable "catalog_name" {
  description = "Unity Catalog name to create schemas under and apply grants against"
  type        = string
  default     = "internet"
}

variable "service_principal_id" {
  description = <<-EOT
    Application ID of the service principal used for:
      - Single-user cluster assignment (compute module)
      - IAM module service principal registration
    Set via TF_VAR_service_principal_id in GitLab CI/CD variables.
  EOT
  type        = string
}

variable "aws_role_arn" {
  description = "IAM role ARN to assume before making AWS API calls. Leave empty to use the current identity (SSO, instance profile, etc.)."
  type        = string
  default     = ""
}

variable "aws_region" {
  description = "AWS region. Required when applying AWS resources (storage, IAM, KMS)."
  type        = string
  default     = "ap-southeast-1"
}

variable "aws_account_id" {
  description = "AWS account ID used for IAM role ARNs in the storage module. Leave empty when applying Databricks-only resources."
  type        = string
  default     = ""
}

variable "gitlab_url" {
  description = "Hostname of the GitLab instance, without scheme (e.g. sgts.gitlab-dedicated.com). Required when applying iam_ci.tf."
  type        = string
  default     = ""
}

variable "gitlab_project_path" {
  description = "Full project path in GitLab used to scope the OIDC trust (e.g. my-group/databricks-terraform). Required when applying iam_ci.tf."
  type        = string
  default     = ""
}

variable "databricks_account_id" {
  description = "Databricks account UUID. Used to scope the workspace S3 bucket trust policy to your specific Databricks account. Required when using the MWS provider (workspace provisioning)."
  type        = string
  default     = ""
  validation {
    condition     = var.databricks_account_id != ""
    error_message = "databricks_account_id must be set. Find it at accounts.cloud.databricks.com under account settings."
  }
}

variable "cross_account_role_name" {
  description = "Name of the Databricks cross-account IAM role for EC2 provisioning. Not present in this account — only needed for classic compute. Set if/when a cross-account role is created."
  type        = string
  default     = "gvt-databricks-internet-cross-account"
}

variable "kms_key_arn" {
  description = "ARN of the Databricks CMK (output of kms.tf). Leave empty on first bootstrap apply before the key exists — falls back to key/*. Set to the kms_key_arn output on subsequent applies to narrow CI role KMS permissions to this key only."
  type        = string
  default     = ""
}

variable "mws_client_id" {
  description = "Application (client) ID of svc-prc-1 — the account-admin service principal used to provision workspaces via the Databricks account API."
  type        = string
  sensitive   = true
  default     = ""
}

variable "mws_client_secret" {
  description = "OAuth client secret for svc-prc-1. Set via TF_VAR_mws_client_secret in GitLab CI/CD variables — never commit to tfvars."
  type        = string
  sensitive   = true
  default     = ""
}