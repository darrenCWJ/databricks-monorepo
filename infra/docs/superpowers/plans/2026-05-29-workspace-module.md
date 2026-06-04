# Workspace Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand `modules/workspace` from a placeholder stub into a fully functional module that provisions a Databricks workspace on AWS with VPC, PrivateLink endpoints, root S3 storage, and Databricks MWS registration.

**Architecture:** All networking (VPC, subnets, IGW, NAT, route tables, security group, VPC endpoints), root S3 storage, cross-account IAM role, and Databricks MWS resources live inside `modules/workspace`. The module is wired into root `main.tf` using the `databricks.mws` provider alias backed by `svc-prc-1` credentials.

**Tech Stack:** Terraform 1.112.0, Databricks provider 1.112.0, AWS provider ~> 5.0, `databricks_mws_*` resources (account-level API).

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `modules/workspace/variables.tf` | Replace | All module inputs — names, CIDRs, AZs, IDs |
| `modules/workspace/main.tf` | Replace | All AWS + Databricks MWS resources |
| `modules/workspace/outputs.tf` | Modify | Point to real MWS workspace outputs |
| `provider.tf` | Modify | Add `databricks.mws` provider alias |
| `variables.tf` | Modify | Add `mws_client_id`, `mws_client_secret` |
| `main.tf` | Modify | Add `module "workspace"` call |

---

### Task 1: Add MWS provider variables and alias

**Files:**
- Modify: `variables.tf`
- Modify: `provider.tf`

- [ ] **Step 1: Add `mws_client_id` and `mws_client_secret` to root `variables.tf`**

Append to the end of `variables.tf`:

```hcl
variable "mws_client_id" {
  description = "Application (client) ID of svc-prc-1 — the account-admin service principal used to provision workspaces via the Databricks account API."
  type        = string
  sensitive   = true
}

variable "mws_client_secret" {
  description = "OAuth client secret for svc-prc-1."
  type        = string
  sensitive   = true
}
```

- [ ] **Step 2: Replace the commented-out `mws` provider alias in `provider.tf`**

Replace the comment block at the bottom of `provider.tf`:

```hcl
# provider "databricks" {
#   alias         = "mws"
#   host          = "https://accounts.cloud.databricks.com"
#   account_id    = var.databricks_account_id
#   client_id     = var.client_id
#   client_secret = var.client_secret
# }
```

With:

```hcl
provider "databricks" {
  alias         = "mws"
  host          = "https://accounts.cloud.databricks.com"
  account_id    = var.databricks_account_id
  client_id     = var.mws_client_id
  client_secret = var.mws_client_secret
}
```

- [ ] **Step 3: Validate syntax**

```bash
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 4: Commit**

```bash
git add provider.tf variables.tf
git commit -m "feat: add databricks mws provider alias and svc-prc-1 credential variables"
```

---

### Task 2: Replace workspace module variables

**Files:**
- Replace: `modules/workspace/variables.tf`

- [ ] **Step 1: Rewrite `modules/workspace/variables.tf`**

Replace the entire file with:

```hcl
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
```

- [ ] **Step 2: Validate**

```bash
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 3: Commit**

```bash
git add modules/workspace/variables.tf
git commit -m "feat: replace workspace module placeholder variables with real inputs"
```

---

### Task 3: Implement AWS networking in workspace module

**Files:**
- Modify: `modules/workspace/main.tf`

- [ ] **Step 1: Replace `modules/workspace/main.tf` with networking resources**

Replace the entire file with:

```hcl
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
  subnet_id     = aws_subnet.private[0].id
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
  description = "Databricks cluster nodes — intra-cluster + HTTPS egress"
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
  vpce_service_relay     = "com.amazonaws.vpce.ap-southeast-1.vpce-svc-0158114c0c730c3bb" # DATAPLANE_RELAY_ACCESS
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
```

- [ ] **Step 2: Validate**

```bash
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 3: Commit**

```bash
git add modules/workspace/main.tf
git commit -m "feat: add VPC, subnets, NAT, security group and PrivateLink endpoints to workspace module"
```

---

### Task 4: Add root S3 bucket and cross-account IAM role

**Files:**
- Modify: `modules/workspace/main.tf`

- [ ] **Step 1: Append S3 root bucket resources to `modules/workspace/main.tf`**

Append to the end of `modules/workspace/main.tf`:

```hcl
# ── Root S3 bucket (DBFS root) ────────────────────────────────────────────────
locals {
  # workspace_name = "gvt_cdo_dev_internet_01" → s3_workspace_slug = "internet-01"
  # Extracts the env+purpose+number segment to keep S3 names concise and consistent
  # with the convention sst-s3-gvt-sdp-databricks-dev-{workspace}-{purpose}.
  s3_workspace_slug = join("-", slice(split("_", var.workspace_name), 2, length(split("_", var.workspace_name))))
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
  bucket = aws_s3_bucket.root.id
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
```

- [ ] **Step 2: Append cross-account IAM role to `modules/workspace/main.tf`**

Append further to the end of `modules/workspace/main.tf`:

```hcl
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
        Sid      = "AllowEc2RunInstancePerVpc"
        Effect   = "Allow"
        Action   = ["ec2:RunInstances"]
        Resource = ["arn:aws:ec2:${var.aws_region}:${var.aws_account_id}:*"]
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
```

- [ ] **Step 3: Validate**

```bash
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 4: Commit**

```bash
git add modules/workspace/main.tf
git commit -m "feat: add root S3 bucket and cross-account IAM role to workspace module"
```

---

### Task 5: Add Databricks MWS resources

**Files:**
- Modify: `modules/workspace/main.tf`
- Modify: `modules/workspace/outputs.tf`

- [ ] **Step 1: Append MWS resources to `modules/workspace/main.tf`**

Append to the end of `modules/workspace/main.tf`:

```hcl
# ── Databricks MWS resources ──────────────────────────────────────────────────
resource "databricks_mws_credentials" "this" {
  provider         = databricks.mws
  credentials_name = "${var.workspace_name}-credentials"
  role_arn         = aws_iam_role.cross_account.arn
}

resource "databricks_mws_storage_configurations" "this" {
  provider                   = databricks.mws
  account_id                 = var.databricks_account_id
  storage_configuration_name = "${var.workspace_name}-storage"
  bucket_name                = aws_s3_bucket.root.bucket
}

resource "databricks_mws_networks" "this" {
  provider           = databricks.mws
  account_id         = var.databricks_account_id
  network_name       = "${var.workspace_name}-network"
  vpc_id             = aws_vpc.this.id
  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.cluster.id]

  vpc_endpoints {
    dataplane_relay = [aws_vpc_endpoint.relay.id]
    rest_api        = [aws_vpc_endpoint.workspace.id]
  }
}

resource "databricks_mws_workspaces" "this" {
  provider       = databricks.mws
  account_id     = var.databricks_account_id
  workspace_name = var.workspace_name
  aws_region     = var.aws_region

  credentials_id           = databricks_mws_credentials.this.credentials_id
  storage_configuration_id = databricks_mws_storage_configurations.this.storage_configuration_id
  network_id               = databricks_mws_networks.this.network_id

  token {}
}
```

- [ ] **Step 2: Update `modules/workspace/outputs.tf`**

Replace the entire file with:

```hcl
output "workspace_id" {
  description = "Databricks workspace ID"
  value       = databricks_mws_workspaces.this.workspace_id
}

output "workspace_url" {
  description = "URL of the provisioned Databricks workspace"
  value       = databricks_mws_workspaces.this.workspace_url
}
```

- [ ] **Step 3: Validate**

```bash
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 4: Commit**

```bash
git add modules/workspace/main.tf modules/workspace/outputs.tf
git commit -m "feat: add databricks MWS credentials, storage, network and workspace resources"
```

---

### Task 6: Wire module into root main.tf

**Files:**
- Modify: `main.tf`

- [ ] **Step 1: Append the workspace module call to root `main.tf`**

Append to the end of `main.tf`:

```hcl
# ── Databricks workspace provisioning ─────────────────────────────────────────
module "workspace" {
  source    = "./modules/workspace"
  providers = { databricks.mws = databricks.mws }

  workspace_name        = "gvt_cdo_dev_internet_01"
  aws_name_prefix       = "sst-gvt-sdp-databricks-dev-internet-01"
  databricks_account_id = var.databricks_account_id
  aws_region            = var.aws_region
  aws_account_id        = var.aws_account_id
  vpc_cidr              = "10.0.0.0/16"
  subnet_cidrs          = ["10.0.1.0/24", "10.0.2.0/24"]
  availability_zones    = ["ap-southeast-1a", "ap-southeast-1b"]
}

output "internet_workspace_url" {
  description = "URL of the internet workspace"
  value       = module.workspace.workspace_url
}
```

- [ ] **Step 2: Run full validate**

```bash
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 3: Set MWS credentials and run plan**

```bash
export TF_VAR_mws_client_id="<svc-prc-1-client-id>"
export TF_VAR_mws_client_secret="<svc-prc-1-client-secret>"
terraform plan -target=module.workspace
```

Review the plan output. Expected resources to create:
- `module.workspace.aws_vpc.this`
- `module.workspace.aws_subnet.private[0]`, `[1]`
- `module.workspace.aws_internet_gateway.this`
- `module.workspace.aws_eip.nat`
- `module.workspace.aws_nat_gateway.this`
- `module.workspace.aws_route_table.public`, `.private`
- `module.workspace.aws_route_table_association.private[0]`, `[1]`
- `module.workspace.aws_security_group.cluster`
- `module.workspace.aws_vpc_endpoint.workspace`, `.relay`
- `module.workspace.aws_s3_bucket.root` (+ versioning, SSE, public access block, policy)
- `module.workspace.aws_iam_role.cross_account` (+ inline policy)
- `module.workspace.databricks_mws_credentials.this`
- `module.workspace.databricks_mws_storage_configurations.this`
- `module.workspace.databricks_mws_networks.this`
- `module.workspace.databricks_mws_workspaces.this`

> **⚠ Pre-apply checklist:**
> - Confirm PrivateLink VPC endpoint service names with Databricks support for `ap-southeast-1` — update the two locals in `modules/workspace/main.tf` if they differ.
> - Confirm `svc-prc-1` has **account admin** role at `accounts.cloud.databricks.com`.
> - Confirm Databricks has PrivateLink enabled on your account.

- [ ] **Step 4: Commit**

```bash
git add main.tf
git commit -m "feat: wire workspace module into root main.tf for gvt_cdo_dev_internet_01"
```
