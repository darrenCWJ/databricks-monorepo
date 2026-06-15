# ADR-0005: Databricks workspace provisioning via self-contained Terraform module

- **Status**: Accepted
- **Date**: 2026-05-29
- **Deciders**: Platform team

## Context

The monorepo needs to provision Databricks workspaces on AWS with VPC networking, PrivateLink endpoints, root S3 storage, cross-account IAM, and Databricks MWS registration. The first workspace is `gvt_cdo_dev_internet_01`.

A placeholder `modules/workspace` stub existed but contained no real resources.

## Decision

All networking, storage, IAM, and Databricks MWS resources live inside a single `modules/workspace` Terraform module. Root `main.tf` instantiates the module with explicit inputs. A dedicated `databricks.mws` provider alias (account-level, backed by `svc-prc-1` credentials) handles workspace creation.

### Module inputs

| Variable | Type | Example |
|---|---|---|
| `workspace_name` | `string` | `gvt_cdo_dev_internet_01` |
| `aws_name_prefix` | `string` | `sst-gvt-sdp-databricks-dev-internet-01` |
| `databricks_account_id` | `string` | (account UUID) |
| `aws_region` | `string` | `ap-southeast-1` |
| `aws_account_id` | `string` | (12-digit) |
| `vpc_cidr` | `string` | `10.0.0.0/16` |
| `subnet_cidrs` | `list(string)` | Two CIDRs, one per AZ |
| `availability_zones` | `list(string)` | Two AZs |

### Module outputs

| Output | Source |
|---|---|
| `workspace_id` | `databricks_mws_workspaces.this.workspace_id` |
| `workspace_url` | `databricks_mws_workspaces.this.workspace_url` |

### Resources created by the module

- VPC with DNS hostnames/resolution enabled
- 2 private subnets across 2 AZs
- Internet gateway, EIP, NAT gateway
- Public and private route tables
- Security group (intra-cluster + HTTPS + port 6666 egress)
- 2 VPC endpoints (PrivateLink): workspace (GENERAL_ACCESS) and relay (DATAPLANE_RELAY_ACCESS)
- Root S3 bucket (versioned, encrypted AES256, public access blocked)
- Cross-account IAM role (trusted by Databricks account `414351767826`)
- `databricks_mws_credentials`, `databricks_mws_storage_configurations`, `databricks_mws_networks`, `databricks_mws_workspaces`

### Provider wiring

A `databricks.mws` provider alias targets `accounts.cloud.databricks.com`. Two sensitive variables (`mws_client_id`, `mws_client_secret`) are set via environment variables, never committed.

## Considered alternatives

- **Separate modules per concern** (one for VPC, one for S3, one for MWS) — rejected: workspace provisioning is a single atomic operation; splitting adds inter-module dependency complexity with no reuse benefit at current scale.
- **Using Databricks Terraform examples directly** — rejected: naming conventions, tagging, and security group rules differ from org standards.

## Consequences

**Positive**
- Self-contained: adding a new workspace is a single module instantiation with different inputs
- Naming is consistent via `aws_name_prefix`
- PrivateLink is enforced from day one

**Negative**
- Module is large (~200 lines); acceptable given it's a single logical unit
- VPC endpoint service names are hardcoded per region; must be updated if deploying to a new region

## Constraints

- Databricks PrivateLink must be enabled on the account before apply
- `svc-prc-1` must have account admin role at `accounts.cloud.databricks.com`
- VPC endpoint service names for `ap-southeast-1` must be confirmed with Databricks support

## Revisit triggers

- Multi-region deployment needed (extract region-specific values to a lookup map)
- More than 5 workspaces provisioned (consider Terragrunt or workspace factory pattern)
