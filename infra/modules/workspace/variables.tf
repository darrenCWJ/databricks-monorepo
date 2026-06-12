variable "workspace_name" {
  description = "Databricks workspace name, e.g. gvt_cdo_dev_internet_01. Used as the display name in the Databricks account console."
  type        = string
}

variable "aws_name_prefix" {
  description = "Prefix for all AWS resource names, e.g. sst-gvt-sdp-databricks-dev-internet-01. Each resource appends its own type and purpose suffix."
  type        = string
}

variable "databricks_account_id" {
  description = "Databricks account UUID — found at accounts.cloud.databricks.com under account settings."
  type        = string
}

variable "trusted_databricks_account_ids" {
  description = "Additional Databricks account UUIDs allowed to assume the cross-account role via sts:ExternalId. Use when a second Databricks account (e.g. a partner tenant) provisions a separate workspace against the same AWS cross-account role."
  type        = list(string)
  default     = []
}

variable "aws_region" {
  description = "AWS region where the workspace will be deployed, e.g. ap-southeast-1."
  type        = string
}

variable "aws_account_id" {
  description = "12-digit AWS account ID, used to construct IAM role ARNs."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the workspace VPC, e.g. 10.0.0.0/16."
  type        = string
}

variable "subnet_cidrs" {
  description = "List of exactly two private subnet CIDRs, one per availability zone, e.g. [\"10.0.1.0/24\", \"10.0.2.0/24\"]. Databricks requires at least /26 per subnet."
  type        = list(string)
  validation {
    condition     = length(var.subnet_cidrs) == 2
    error_message = "Exactly two subnet CIDRs are required (one per availability zone)."
  }
}

variable "availability_zones" {
  description = "List of exactly two AZ names corresponding to subnet_cidrs, e.g. [\"ap-southeast-1a\", \"ap-southeast-1b\"]."
  type        = list(string)
  validation {
    condition     = length(var.availability_zones) == 2
    error_message = "Exactly two availability zones are required."
  }
}

variable "managed_services_cmk_arn" {
  description = "ARN of the KMS CMK for Databricks managed services (notebooks, secrets, query results)."
  type        = string
}

variable "managed_services_cmk_alias" {
  description = "Alias name of the managed-services CMK (e.g. alias/foo-cmk-managedservices)."
  type        = string
}

variable "storage_cmk_arn" {
  description = "ARN of the KMS CMK for Databricks storage (S3 root bucket and EBS volumes)."
  type        = string
}

variable "storage_cmk_alias" {
  description = "Alias name of the storage CMK (e.g. alias/foo-cmk-storage)."
  type        = string
}
