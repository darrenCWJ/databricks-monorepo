# Workspace Module Design
**Date:** 2026-05-29  
**Status:** Approved

## Overview

Expand `modules/workspace` from a placeholder stub into a fully functional Terraform module that provisions a complete Databricks workspace on AWS, including VPC networking, PrivateLink endpoints, root S3 storage, and Databricks MWS registration.

The first workspace to be provisioned is `gvt_cdo_dev_internet_01`.

## Approach

All networking, storage, and Databricks MWS resources live inside `modules/workspace`. Root `main.tf` instantiates the module with explicit inputs. This keeps workspace provisioning self-contained and reusable for future workspaces.

## Module Inputs

| Variable | Type | Value for `gvt_cdo_dev_internet_01` |
|---|---|---|
| `workspace_name` | `string` | `gvt_cdo_dev_internet_01` |
| `aws_name_prefix` | `string` | `sst-gvt-sdp-databricks-dev-internet-01` |
| `databricks_account_id` | `string` | `b952c76b-09ec-4f6b-a6a0-b0d5cc5a2e4f` |
| `aws_region` | `string` | `ap-southeast-1` |
| `aws_account_id` | `string` | `721140971379` |
| `vpc_cidr` | `string` | `10.0.0.0/16` |
| `subnet_cidrs` | `list(string)` | `["10.0.1.0/24", "10.0.2.0/24"]` |
| `availability_zones` | `list(string)` | `["ap-southeast-1a", "ap-southeast-1b"]` |

## Module Outputs

| Output | Source |
|---|---|
| `workspace_id` | `databricks_mws_workspaces.this.workspace_id` |
| `workspace_url` | `databricks_mws_workspaces.this.workspace_url` |

## AWS Networking Resources

All named using `aws_name_prefix` with a purpose suffix. The VPC has DNS hostnames and DNS resolution enabled (required by Databricks).

| Resource | Name |
|---|---|
| `aws_vpc` | `{prefix}-network` |
| `aws_subnet` (x2) | `{prefix}-a`, `{prefix}-b` |
| `aws_internet_gateway` | `{prefix}-public` |
| `aws_eip` | `{prefix}-nat` |
| `aws_nat_gateway` | `{prefix}-egress` (in subnet-a) |
| `aws_route_table` (public) | `{prefix}-public` — `0.0.0.0/0` → IGW |
| `aws_route_table` (private) | `{prefix}-private` — `0.0.0.0/0` → NAT; associated to both subnets |
| `aws_security_group` | `{prefix}-cluster` — allows all inbound/outbound within the SG, TCP 443 outbound |
| `aws_vpc_endpoint` (workspace) | `{prefix}-workspace` — Interface, GENERAL_ACCESS |
| `aws_vpc_endpoint` (relay) | `{prefix}-relay` — Interface, DATAPLANE_RELAY_ACCESS |
| `aws_s3_bucket` (root) | `sst-s3-gvt-sdp-databricks-dev-internet-01-root` |

Both VPC endpoints are associated to both subnets and the cluster security group. Private DNS is enabled on both.

## S3 Root Bucket

Name: `sst-s3-gvt-sdp-databricks-dev-internet-01-root`

Follows the project naming convention `sst-s3-gvt-sdp-databricks-dev-{workspace}-{purpose}`. Configured with:
- Versioning enabled
- Public access block (all four settings enabled)
- No KMS — uses default AES256 (workspace root storage does not require CMK; CMK is reserved for Unity Catalog data buckets)

## Cross-Account IAM Role

Name: `sst-iam-gvt-sdp-databricks-dev-internet-01-crossaccount`

Trust policy allows `arn:aws:iam::414351767826:root` (Databricks production account) to assume the role. Used by Databricks to provision/terminate EC2 cluster nodes. Registered with Databricks via `databricks_mws_credentials`.

## Databricks MWS Resources

All use the `databricks.mws` provider alias (account-level, targeting `accounts.cloud.databricks.com`).

| Resource | Purpose |
|---|---|
| `databricks_mws_credentials` | Registers cross-account IAM role |
| `databricks_mws_storage_configurations` | Registers root S3 bucket |
| `databricks_mws_networks` | Registers VPC, subnets, SG, VPC endpoint IDs |
| `databricks_mws_workspaces` | Creates workspace, wires the three above |

## Provider Wiring

A new `databricks.mws` provider alias is added to `provider.tf`:

```hcl
provider "databricks" {
  alias         = "mws"
  host          = "https://accounts.cloud.databricks.com"
  account_id    = var.databricks_account_id
  client_id     = var.mws_client_id
  client_secret = var.mws_client_secret
}
```

Two new sensitive variables are added to root `variables.tf`:
- `mws_client_id` — application ID of `svc-prc-1`
- `mws_client_secret` — OAuth secret of `svc-prc-1`

Set via `TF_VAR_mws_client_id` / `TF_VAR_mws_client_secret` environment variables. Never committed to `terraform.tfvars`.

The workspace module declares `required_providers` with `databricks.mws` configuration alias and accepts it via `providers` in the module call.

## Root main.tf Module Call

```hcl
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
```

## File Changes

| File | Change |
|---|---|
| `modules/workspace/main.tf` | Replace placeholder locals with real AWS + MWS resources |
| `modules/workspace/variables.tf` | Replace existing vars, add `aws_name_prefix`, `vpc_cidr`, `subnet_cidrs`, `availability_zones`, `aws_account_id` |
| `modules/workspace/outputs.tf` | Update to reference `databricks_mws_workspaces.this.*` |
| `provider.tf` | Uncomment and populate `databricks.mws` provider alias |
| `variables.tf` | Add `mws_client_id`, `mws_client_secret` (sensitive) |
| `main.tf` | Add `module "workspace"` call |

## Constraints

- Databricks PrivateLink must be enabled on the account before `terraform apply` — raise a support ticket with Databricks if not already done.
- The `svc-prc-1` service principal must have **account admin** role in the Databricks account console (`accounts.cloud.databricks.com`).
- VPC endpoint service names for `ap-southeast-1` must be confirmed — they follow the pattern `com.amazonaws.vpce.ap-southeast-1.vpce-svc-<id>` and are provided by Databricks per account.
