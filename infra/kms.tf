# ── Managed Services CMK ──────────────────────────────────────────────────────
# Encrypts Databricks control-plane data: notebooks, secrets, query results.
# Databricks control plane (414351767826) must be able to Encrypt/Decrypt.

resource "aws_kms_key" "managed_services_cmk" {
  description             = "Databricks managed services CMK (${var.aws_account_id})"
  enable_key_rotation     = true
  deletion_window_in_days = 30

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnableIAMPolicies"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${var.aws_account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid    = "AllowDatabricksControlPlane"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::414351767826:root"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:PrincipalTag/DatabricksAccountId" = [var.databricks_account_id]
          }
        }
      },
    ]
  })

  tags = {
    Name    = "databricks-managed-services-cmk"
    Purpose = "Databricks managed services encryption"
  }
}

resource "aws_kms_alias" "managed_services_cmk" {
  name          = "alias/sdp-databricks-managedservices-dev"
  target_key_id = aws_kms_key.managed_services_cmk.key_id
}

# ── Storage CMK ───────────────────────────────────────────────────────────────
# Encrypts workspace root S3 bucket objects and EBS volumes on cluster nodes.
# Databricks control plane needs broader grants; cross-account role needs
# Decrypt/GenerateDataKey for EBS (via ec2 service).

resource "aws_kms_key" "storage_cmk" {
  description             = "Databricks storage CMK (${var.aws_account_id})"
  enable_key_rotation     = true
  deletion_window_in_days = 30

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnableIAMPolicies"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${var.aws_account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid    = "AllowDatabricksControlPlaneDBFS"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::414351767826:root"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:PrincipalTag/DatabricksAccountId" = [var.databricks_account_id]
          }
        }
      },
      {
        Sid    = "AllowDatabricksControlPlaneDBFSGrants"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::414351767826:root"
        }
        Action = [
          "kms:CreateGrant",
          "kms:ListGrants",
          "kms:RevokeGrant",
        ]
        Resource = "*"
        Condition = {
          Bool = {
            "kms:GrantIsForAWSResource" = "true"
          }
          StringEquals = {
            "aws:PrincipalTag/DatabricksAccountId" = [var.databricks_account_id]
          }
        }
      },
      {
        Sid    = "AllowCrossAccountRoleEBS"
        Effect = "Allow"
        Principal = {
          AWS = data.aws_iam_role.cross_account.arn
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey*",
          "kms:CreateGrant",
          "kms:DescribeKey",
        ]
        Resource = "*"
        Condition = {
          StringLike = {
            "kms:ViaService" = "ec2.*.amazonaws.com"
          }
        }
      },
      {
        Sid       = "S3ServiceEncryption"
        Effect    = "Allow"
        Principal = { Service = "s3.amazonaws.com" }
        Action = [
          "kms:GenerateDataKey*",
          "kms:Decrypt",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:CallerAccount" = var.aws_account_id
          }
        }
      },
    ]
  })

  tags = {
    Name    = "databricks-storage-cmk"
    Purpose = "Databricks storage encryption (S3 root bucket + EBS)"
  }
}

resource "aws_kms_alias" "storage_cmk" {
  name          = "alias/sdp-databricks-storage-dev"
  target_key_id = aws_kms_key.storage_cmk.key_id
}

output "kms_managed_services_key_arn" {
  description = "ARN of the managed-services CMK"
  value       = aws_kms_key.managed_services_cmk.arn
}

output "kms_storage_key_arn" {
  description = "ARN of the storage CMK — pass as kms_key_arn to each storage module call"
  value       = aws_kms_key.storage_cmk.arn
}
