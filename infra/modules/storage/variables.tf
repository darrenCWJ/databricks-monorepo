variable "aws_account_id" {
  description = "AWS account ID (not Databricks account ID)"
  type        = string
}

variable "bucket_name_override" {
  description = "Override the derived bucket name. Use when the bucket was created outside this module (e.g. the workspace root bucket)."
  type        = string
  default     = null
}

variable "skip_bucket_creation" {
  description = "Set to true to skip S3 bucket creation. Use when the bucket is managed elsewhere (e.g. the workspace root bucket). Requires bucket_name_override."
  type        = bool
  default     = false
}

variable "external_location_name" {
  description = "Name for the Unity Catalog external location. Not used when purpose = 'workspace'."
  type        = string
  default     = ""
}

variable "storage_credential_name" {
  description = "Name for the Unity Catalog storage credential. Not used when purpose = 'workspace'."
  type        = string
  default     = ""
}

variable "iam_role_name" {
  description = "Name for the IAM role that Unity Catalog or Databricks will assume"
  type        = string
}

variable "enable_kms" {
  description = "Set to true to enable CMK encryption on the S3 bucket. Must be set statically — cannot be derived from a resource ARN."
  type        = bool
  default     = false
}

variable "kms_key_arn" {
  description = "ARN of the KMS CMK to use for bucket encryption. Required when enable_kms = true."
  type        = string
  default     = null
}

variable "read_only" {
  description = "Set to true to limit the external location to read-only access. Not used when purpose = 'workspace'."
  type        = bool
  default     = false
}

variable "enable_file_events" {
  description = "Set to true to attach the SQS/SNS file-events policy required for Auto Loader file notification mode"
  type        = bool
  default     = false
}

variable "databricks_account_id" {
  description = "Databricks account ID. Required when purpose = 'workspace' — used as the external ID in the cross-account trust policy and in the bucket policy condition."
  type        = string
  default     = ""
}

variable "external_location_grants" {
  description = "Map of principal → list of privileges on the external location. Not used when purpose = 'workspace'."
  type        = map(list(string))

  validation {
    condition = alltrue([
      for privileges in values(var.external_location_grants) :
      alltrue([
        for p in privileges :
        contains(["READ_FILES", "WRITE_FILES", "CREATE_EXTERNAL_TABLE", "CREATE_EXTERNAL_VOLUME", "MANAGE"], p)
      ])
    ])
    error_message = "Each privilege must be one of: READ_FILES, WRITE_FILES, CREATE_EXTERNAL_TABLE, CREATE_EXTERNAL_VOLUME, MANAGE."
  }
  default = {}
}

# ── Optional Unity Catalog catalogs ─────────────────────────────────────────
# Pass a map of catalog_name => subdir to create one catalog per entry, each
# rooted at s3://<bucket>/<subdir>. Leave empty (the default) to skip catalog
# creation entirely — useful for landing/autoloader/workspace buckets that
# don't need their own catalogs.
#
# Example:
#   catalogs = {
#     dev_admin  = "admin"
#     dev_bronze = "bronze"
#   }

variable "catalogs" {
  description = "Map of catalog name → object with subdir (S3 prefix) and owner (SP application ID). Leave empty to skip catalog creation."
  type = map(object({
    subdir = string
    owner  = optional(string, null)
  }))
  default = {}
}

variable "env" {
  type        = string
  description = "Environment in which the bucket is going to be used."

  validation {
    condition     = contains(["dev", "stg", "prd"], var.env)
    error_message = "Must be one of: dev, stg, prd."
  }
}

variable "purpose" {
  type        = string
  description = "Purpose of the S3 bucket. Drives trust policy and Databricks resource type."

  validation {
    condition     = contains(["data", "landing", "autoloader", "workspace"], var.purpose)
    error_message = "Must be one of: data, landing, autoloader, workspace."
  }
}
