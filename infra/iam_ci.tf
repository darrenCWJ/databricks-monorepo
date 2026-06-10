# ── GitLab CI OIDC authentication ────────────────────────────────
# One-time bootstrap: apply this manually once using temporary local credentials.
# After that, GitLab CI uses the role created here — no static keys needed.

data "tls_certificate" "gitlab" {
  url = "https://${var.gitlab_url}"
}

resource "aws_iam_openid_connect_provider" "gitlab" {
  url             = "https://${var.gitlab_url}"
  client_id_list  = ["https://${var.gitlab_url}"]
  thumbprint_list = [data.tls_certificate.gitlab.certificates[0].sha1_fingerprint]
}

resource "aws_iam_role" "gitlab_ci" {
  name = "gitlab-ci-databricks-terraform"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.gitlab.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        # Any branch of the specific project can authenticate.
        # Apply is further restricted to main by GitLab CI (when: manual + only: main).
        StringLike = {
          "${var.gitlab_url}:sub" = "project_path:${var.gitlab_project_path}:ref_type:branch:ref:*"
        }
        StringEquals = {
          "${var.gitlab_url}:aud" = "https://${var.gitlab_url}"
        }
      }
    }]
  })
}

resource "aws_iam_policy" "gitlab_ci_terraform" {
  name        = "gitlab-ci-databricks-terraform"
  description = "Permissions for GitLab CI to run Terraform for the Databricks infrastructure project"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3OpsAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:DeleteObject",
        ]
        Resource = [
          "arn:aws:s3:::sst-s3-gvt-sdp-databricks-internet-workspace",
          "arn:aws:s3:::sst-s3-gvt-sdp-databricks-internet-workspace/*",
        ]
      },
      {
        Sid    = "S3BucketManagement"
        Effect = "Allow"
        Action = [
          "s3:CreateBucket",
          "s3:DeleteBucket",
          "s3:GetBucketLocation",
          "s3:GetBucketAcl",
          "s3:GetBucketPolicy",
          "s3:PutBucketPolicy",
          "s3:DeleteBucketPolicy",
          "s3:GetBucketTagging",
          "s3:PutBucketTagging",
          "s3:ListBucket",
          "s3:GetBucketNotification",
          "s3:PutBucketNotification",
          "s3:GetLifecycleConfiguration",
          "s3:PutLifecycleConfiguration",
          "s3:GetBucketVersioning",
          "s3:PutBucketVersioning",
          "s3:GetEncryptionConfiguration",
          "s3:PutEncryptionConfiguration",
          "s3:GetBucketPublicAccessBlock",
          "s3:PutPublicAccessBlock",
        ]
        Resource = ["arn:aws:s3:::sst-s3-gvt-sdp-databricks-*"]
      },
      {
        Sid    = "EC2ManagementForDatabricksVPC"
        Effect = "Allow"
        Action = [
          "ec2:DescribeVpcs",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeInternetGateways",
          "ec2:DescribeNatGateways",
          "ec2:DescribeRouteTables",
          "ec2:DescribeAddresses",
          "ec2:DescribeVpcEndpoints",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeAvailabilityZones",
          "ec2:CreateVpc",
          "ec2:DeleteVpc",
          "ec2:ModifyVpcAttribute",
          "ec2:CreateSubnet",
          "ec2:DeleteSubnet",
          "ec2:ModifySubnetAttribute",
          "ec2:CreateInternetGateway",
          "ec2:DeleteInternetGateway",
          "ec2:AttachInternetGateway",
          "ec2:DetachInternetGateway",
          "ec2:AllocateAddress",
          "ec2:ReleaseAddress",
          "ec2:CreateNatGateway",
          "ec2:DeleteNatGateway",
          "ec2:CreateRouteTable",
          "ec2:DeleteRouteTable",
          "ec2:CreateRoute",
          "ec2:DeleteRoute",
          "ec2:AssociateRouteTable",
          "ec2:DisassociateRouteTable",
          "ec2:CreateSecurityGroup",
          "ec2:DeleteSecurityGroup",
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:AuthorizeSecurityGroupEgress",
          "ec2:RevokeSecurityGroupIngress",
          "ec2:RevokeSecurityGroupEgress",
          "ec2:CreateVpcEndpoint",
          "ec2:DeleteVpcEndpoints",
          "ec2:ModifyVpcEndpoint",
          "ec2:CreateTags",
          "ec2:DeleteTags",
        ]
        Resource = ["*"]
      },
      {
        # iam:ListRoles is a list-only action — AWS requires Resource: "*" for all list operations.
        Sid      = "IAMGlobalList"
        Effect   = "Allow"
        Action   = ["iam:ListRoles"]
        Resource = ["*"]
      },
      {
        Sid    = "IAMRoleAndPolicyManagement"
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:GetRole",
          "iam:UpdateRole",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:UpdateAssumeRolePolicy",
          "iam:PutRolePolicy",
          "iam:GetRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:CreatePolicy",
          "iam:DeletePolicy",
          "iam:GetPolicy",
          "iam:GetPolicyVersion",
          "iam:ListPolicyVersions",
          "iam:CreatePolicyVersion",
          "iam:DeletePolicyVersion",
          "iam:TagPolicy",
          "iam:UntagPolicy",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:ListAttachedRolePolicies",
          "iam:ListRolePolicies",
          "iam:PassRole",
        ]
        Resource = [
          "arn:aws:iam::${var.aws_account_id}:role/unity-catalog-*",
          "arn:aws:iam::${var.aws_account_id}:role/gitlab-ci-*",
          "arn:aws:iam::${var.aws_account_id}:role/sst-gvt-sdp-databricks-*",
          "arn:aws:iam::${var.aws_account_id}:policy/unity-catalog-*",
          "arn:aws:iam::${var.aws_account_id}:policy/gitlab-ci-*",
        ]
      },
      {
        Sid    = "OIDCProviderManagement"
        Effect = "Allow"
        Action = [
          "iam:CreateOpenIDConnectProvider",
          "iam:DeleteOpenIDConnectProvider",
          "iam:GetOpenIDConnectProvider",
          "iam:UpdateOpenIDConnectProviderThumbprint",
          "iam:TagOpenIDConnectProvider",
        ]
        Resource = ["arn:aws:iam::${var.aws_account_id}:oidc-provider/${var.gitlab_url}"]
      },
      {
        # CreateKey, ListKeys, ListAliases must always be on * — no key ARN
        # exists yet during creation, and list actions are not key-specific.
        Sid    = "KMSGlobalActions"
        Effect = "Allow"
        Action = [
          "kms:CreateKey",
          "kms:ListKeys",
          "kms:ListAliases",
        ]
        Resource = ["*"]
      },
      {
        # CI needs to manage the CMK lifecycle via Terraform (create, update tags,
        # schedule deletion). Data-plane operations (encrypt/decrypt) are NOT needed
        # here — those are granted to the Unity Catalog IAM roles by the storage
        # module's s3_access policy, not to the CI role.
        #
        # Scoped to the specific CMK ARN once kms_key_arn is set (post-bootstrap).
        # Falls back to key/* on first apply before the key exists.
        Sid    = "KMSKeyManagement"
        Effect = "Allow"
        Action = [
          "kms:DescribeKey",
          "kms:GetKeyPolicy",
          "kms:GetKeyRotationStatus",
          "kms:ListResourceTags",
          "kms:PutKeyPolicy",
          "kms:EnableKeyRotation",
          "kms:DisableKeyRotation",
          "kms:TagResource",
          "kms:UntagResource",
          "kms:ScheduleKeyDeletion",
          "kms:CancelKeyDeletion",
          "kms:CreateAlias",
          "kms:DeleteAlias",
          "kms:UpdateAlias",
        ]
        Resource = var.kms_key_arn != "" ? [
          var.kms_key_arn,
          "arn:aws:kms:*:${var.aws_account_id}:alias/sdp-databricks-*",
          ] : [
          "arn:aws:kms:*:${var.aws_account_id}:key/*",
          "arn:aws:kms:*:${var.aws_account_id}:alias/sdp-databricks-*",
        ]
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "gitlab_ci_terraform" {
  role       = aws_iam_role.gitlab_ci.name
  policy_arn = aws_iam_policy.gitlab_ci_terraform.arn
}

output "gitlab_ci_role_arn" {
  description = "Set this as GITLAB_CI_AWS_ROLE_ARN in GitLab CI/CD variables (Settings > CI/CD > Variables)"
  value       = aws_iam_role.gitlab_ci.arn
}
