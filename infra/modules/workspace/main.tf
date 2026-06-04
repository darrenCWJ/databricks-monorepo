terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    databricks = {
      source                = "databricks/databricks"
      version               = "= 1.112.0"
      configuration_aliases = [databricks.mws]
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.9"
    }
  }
}

# ── VPC ───────────────────────────────────────────────────────────────────────
resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = { Name = "${var.aws_name_prefix}-network" }
}

# ── Subnets ───────────────────────────────────────────────────────────────────
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = { Name = "${var.aws_name_prefix}-${count.index == 0 ? "a" : "b"}" }
}

# NAT gateway requires a public subnet — use a dedicated /28 per AZ carved out of the VPC.
# These are not passed to Databricks; only the private subnets are registered.
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 12, count.index + 10)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = false

  tags = { Name = "${var.aws_name_prefix}-public-${count.index == 0 ? "a" : "b"}" }
}

# ── Internet gateway + NAT ────────────────────────────────────────────────────
resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.aws_name_prefix}-public" }
}

resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = { Name = "${var.aws_name_prefix}-nat" }
}

resource "aws_nat_gateway" "this" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  tags          = { Name = "${var.aws_name_prefix}-egress" }
  depends_on    = [aws_internet_gateway.this]
}

# ── Route tables ──────────────────────────────────────────────────────────────
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
  tags = { Name = "${var.aws_name_prefix}-public" }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this.id
  }
  tags = { Name = "${var.aws_name_prefix}-private" }
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# ── Security group ────────────────────────────────────────────────────────────
# Databricks requires: all intra-cluster traffic allowed, TCP 443 outbound.
resource "aws_security_group" "cluster" {
  name        = "${var.aws_name_prefix}-cluster"
  description = "Databricks cluster nodes - intra-cluster + HTTPS egress"
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "All traffic within the security group (intra-cluster)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    description = "All traffic within the security group (intra-cluster)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    description = "HTTPS to Databricks control plane and AWS services"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Metastore and data plane relay (port 6666)"
    from_port   = 6666
    to_port     = 6666
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.aws_name_prefix}-cluster" }
}

# ── VPC endpoints (PrivateLink) ───────────────────────────────────────────────
# Service names are region-specific and provided by Databricks.
# ap-southeast-1 values: confirm with Databricks support before apply.
locals {
  vpce_service_workspace = "com.amazonaws.vpce.ap-southeast-1.vpce-svc-02535b257fc253ff4" # GENERAL_ACCESS
  vpce_service_relay     = "com.amazonaws.vpce.ap-southeast-1.vpce-svc-0557367c6fc1a0c5c" # DATAPLANE_RELAY_ACCESS
}

resource "aws_vpc_endpoint" "workspace" {
  vpc_id              = aws_vpc.this.id
  service_name        = local.vpce_service_workspace
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.cluster.id]
  private_dns_enabled = true

  tags = { Name = "${var.aws_name_prefix}-workspace" }
}

resource "aws_vpc_endpoint" "relay" {
  vpc_id              = aws_vpc.this.id
  service_name        = local.vpce_service_relay
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.cluster.id]
  private_dns_enabled = true

  tags = { Name = "${var.aws_name_prefix}-relay" }
}

# ── Root S3 bucket (DBFS root) ────────────────────────────────────────────────
locals {
  # workspace_name = "gvt_cdo_dev_internet_01" → s3_workspace_slug = "internet-01"
  # Strips the gvt_cdo_ prefix (indices 0,1,2) leaving dev_internet_01 → "internet-01"
  # Wait — we want "internet-01" not "dev-internet-01", so strip indices 0..2, start from 3.
  s3_workspace_slug = join("-", slice(split("_", var.workspace_name), 3, length(split("_", var.workspace_name))))
  root_bucket_name  = "sst-s3-gvt-sdp-databricks-dev-${local.s3_workspace_slug}-root"
}

resource "aws_s3_bucket" "root" {
  bucket = local.root_bucket_name
  tags   = { Name = local.root_bucket_name }
}

resource "aws_s3_bucket_versioning" "root" {
  bucket = aws_s3_bucket.root.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "root" {
  bucket = aws_s3_bucket.root.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "root" {
  bucket                  = aws_s3_bucket.root.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "root" {
  bucket     = aws_s3_bucket.root.id
  depends_on = [aws_s3_bucket_public_access_block.root]
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::414351767826:root" }
      Action = [
        "s3:GetObject", "s3:GetObjectVersion", "s3:PutObject",
        "s3:DeleteObject", "s3:ListBucket", "s3:GetBucketLocation",
      ]
      Resource = [
        "arn:aws:s3:::${local.root_bucket_name}/*",
        "arn:aws:s3:::${local.root_bucket_name}",
      ]
      Condition = {
        StringEquals = {
          "aws:PrincipalTag/DatabricksAccountId" = var.databricks_account_id
        }
      }
    }]
  })
}

# ── Cross-account IAM role ────────────────────────────────────────────────────
resource "aws_iam_role" "cross_account" {
  name = "${var.aws_name_prefix}-crossaccount"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::414351767826:root" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "sts:ExternalId" = var.databricks_account_id }
      }
    }]
  })

  tags = { Name = "${var.aws_name_prefix}-crossaccount" }
}

resource "aws_iam_role_policy" "cross_account" {
  name = "${var.aws_name_prefix}-crossaccount-policy"
  role = aws_iam_role.cross_account.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "NonResourceBasedPermissions"
        Effect = "Allow"
        Action = [
          "ec2:CancelSpotInstanceRequests",
          "ec2:RequestSpotInstances",
          "ec2:DescribeAvailabilityZones",
          "ec2:DescribeIamInstanceProfileAssociations",
          "ec2:DescribeInstanceStatus",
          "ec2:DescribeInstances",
          "ec2:DescribeInternetGateways",
          "ec2:DescribeNatGateways",
          "ec2:DescribeNetworkAcls",
          "ec2:DescribeRouteTables",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeSpotInstanceRequests",
          "ec2:DescribeSpotPriceHistory",
          "ec2:DescribeSubnets",
          "ec2:DescribeVolumes",
          "ec2:DescribeVpcAttribute",
          "ec2:DescribeVpcs",
          "ec2:CreateTags",
          "ec2:DeleteTags",
        ]
        Resource = ["*"]
      },
      {
        Sid    = "InstancePoolsSupport"
        Effect = "Allow"
        Action = [
          "ec2:AssociateIamInstanceProfile",
          "ec2:DisassociateIamInstanceProfile",
          "ec2:ReplaceIamInstanceProfileAssociation",
        ]
        Resource = ["arn:aws:ec2:${var.aws_region}:${var.aws_account_id}:instance/*"]
        Condition = {
          StringEquals = {
            "ec2:ResourceTag/Vendor" = "Databricks"
          }
        }
      },
      {
        # Required so Databricks can attach an IAM instance profile to cluster EC2 nodes.
        # Without this, ec2:RunInstances fails with UnauthorizedOperation even when the
        # RunInstances permission itself is present.
        Sid    = "AllowPassRoleForInstanceProfiles"
        Effect = "Allow"
        Action = ["iam:PassRole"]
        Resource = ["arn:aws:iam::${var.aws_account_id}:instance-profile/*"]
      },
      {
        # RunInstances touches multiple resource types: instances, network interfaces,
        # volumes, and security groups (all account-scoped) plus AMIs (no account ID in ARN).
        # Using * is the documented Databricks requirement — cannot be scoped further
        # because AMI ARNs omit the account ID.
        Sid      = "AllowEc2RunInstancePerVpc"
        Effect   = "Allow"
        Action   = ["ec2:RunInstances"]
        Resource = ["*"]
      },
      {
        Sid    = "AllowEc2TerminateInstances"
        Effect = "Allow"
        Action = ["ec2:TerminateInstances"]
        Resource = ["arn:aws:ec2:${var.aws_region}:${var.aws_account_id}:instance/*"]
        Condition = {
          StringEquals = {
            "ec2:ResourceTag/Vendor" = "Databricks"
          }
        }
      },
    ]
  })
}

# ── Databricks MWS resources ──────────────────────────────────────────────────
# IAM role changes take ~10s to propagate globally before Databricks can validate them.
resource "time_sleep" "iam_propagation" {
  create_duration = "15s"
  depends_on      = [aws_iam_role_policy.cross_account]
}

resource "databricks_mws_credentials" "this" {
  provider         = databricks.mws
  credentials_name = "${var.workspace_name}-credentials"
  role_arn         = aws_iam_role.cross_account.arn
  depends_on       = [time_sleep.iam_propagation]
}

resource "databricks_mws_storage_configurations" "this" {
  provider                   = databricks.mws
  account_id                 = var.databricks_account_id
  storage_configuration_name = "${var.workspace_name}-storage"
  bucket_name                = aws_s3_bucket.root.bucket
}

resource "databricks_mws_vpc_endpoint" "workspace" {
  provider            = databricks.mws
  account_id          = var.databricks_account_id
  aws_vpc_endpoint_id = aws_vpc_endpoint.workspace.id
  vpc_endpoint_name   = "${var.workspace_name}-vpce-workspace"
  region              = var.aws_region
}

resource "databricks_mws_vpc_endpoint" "relay" {
  provider            = databricks.mws
  account_id          = var.databricks_account_id
  aws_vpc_endpoint_id = aws_vpc_endpoint.relay.id
  vpc_endpoint_name   = "${var.workspace_name}-vpce-relay"
  region              = var.aws_region
}

resource "databricks_mws_networks" "this" {
  provider           = databricks.mws
  account_id         = var.databricks_account_id
  network_name       = "${var.workspace_name}-network"
  vpc_id             = aws_vpc.this.id
  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.cluster.id]

  vpc_endpoints {
    dataplane_relay = [databricks_mws_vpc_endpoint.relay.vpc_endpoint_id]
    rest_api        = [databricks_mws_vpc_endpoint.workspace.vpc_endpoint_id]
  }
}

resource "databricks_mws_private_access_settings" "this" {
  provider                     = databricks.mws
  account_id                   = var.databricks_account_id
  private_access_settings_name = "${var.workspace_name}-pas"
  region                       = var.aws_region
  public_access_enabled        = true
}

resource "databricks_mws_workspaces" "this" {
  provider       = databricks.mws
  account_id     = var.databricks_account_id
  workspace_name = var.workspace_name
  aws_region     = var.aws_region

  credentials_id             = databricks_mws_credentials.this.credentials_id
  storage_configuration_id   = databricks_mws_storage_configurations.this.storage_configuration_id
  network_id                 = databricks_mws_networks.this.network_id
  private_access_settings_id = databricks_mws_private_access_settings.this.private_access_settings_id

  token {}
}
