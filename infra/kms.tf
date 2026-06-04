# ── Customer Managed Key (CMK) for S3 bucket encryption ──────────
#
# Why CMK instead of AWS-managed KMS keys?
#   - AWS-managed keys (aws/s3) are controlled entirely by AWS. You cannot
#     set key policies, audit who uses them, or revoke access independently.
#   - A CMK gives you ownership: you define who can use/manage the key,
#     enable automatic rotation, and can disable/delete it if needed.
#
# One shared CMK is used for all 4 S3 buckets in this project.
# This is standard practice — fewer keys means a simpler audit trail
# and one rotation schedule to manage.

resource "aws_kms_key" "s3" {
  description = "CMK for Databricks S3 buckets (${var.aws_account_id})"

  # Automatically rotates the key's backing cryptographic material every year.
  # Important: rotation does NOT re-encrypt existing data — S3 keeps a reference
  # to which key version encrypted each object, so old data is still readable.
  # New uploads will use the new key material going forward.
  enable_key_rotation = true

  # KMS keys cannot be deleted immediately. This sets a 30-day waiting window
  # before deletion completes, giving time to catch accidental deletes.
  # Minimum is 7 days; 30 is a safer default for production data.
  deletion_window_in_days = 30

  # ── Key policy ─────────────────────────────────────────────────
  # A KMS key has TWO access control layers:
  #   1. The key policy (defined here) — controls who CAN be granted access
  #   2. IAM policies on individual roles — controls who actually HAS access
  #
  # Both layers must allow an action for it to succeed.
  # Exception: the root account statement below allows IAM policies to
  # delegate access without needing changes to the key policy each time.
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # The root account has full control over the key.
        #
        # Critically, this statement also "enables IAM" — it means IAM policies
        # attached to roles in this account can grant those roles access to this
        # key. Without this, IAM policies alone are not enough; the key policy
        # itself must explicitly list every role that needs access.
        #
        # The Unity Catalog IAM roles (created by the storage module) get their
        # kms:Encrypt/Decrypt permissions via aws_iam_policy.s3_access, which
        # works because of this root statement.
        Sid       = "EnableIAMPolicies"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${var.aws_account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        # S3 needs to call KMS on behalf of the bucket when enforcing
        # server-side encryption — for example when replicating objects or
        # during certain multipart upload operations. The S3 service principal
        # must be listed directly in the key policy because it is not an IAM
        # role in your account, so the root statement above does not cover it.
        Sid       = "S3ServiceEncryption"
        Effect    = "Allow"
        Principal = { Service = "s3.amazonaws.com" }
        Action = [
          "kms:GenerateDataKey*", # generates the per-object data key
          "kms:Decrypt",          # needed when S3 re-encrypts (e.g. replication)
        ]
        Resource = "*"
        Condition = {
          # Scope this permission to S3 operations originating from your account
          # only, so the S3 service principal cannot use this key for other accounts.
          StringEquals = {
            "kms:CallerAccount" = var.aws_account_id
          }
        }
      },
    ]
  })

  tags = {
    Name    = "databricks-s3-cmk"
    Purpose = "S3 bucket encryption for Databricks Unity Catalog"
  }
}

# A human-readable alias for the key.
# The key ID (e.g. mrk-abc123) is not meaningful on its own; the alias makes
# it easy to identify in the AWS console and in CloudTrail audit logs.
resource "aws_kms_alias" "s3" {
  name          = "alias/sdp-databricks-s3-dev"
  target_key_id = aws_kms_key.s3.key_id
}

output "kms_key_arn" {
  description = "ARN of the CMK — pass as kms_key_arn to each storage module call"
  value       = aws_kms_key.s3.arn
}
