# infra

Terraform project that provisions a Databricks workspace environment on AWS — VPC networking, MWS workspace, Unity Catalog identities and data layers, compute policies, S3 storage with CMK encryption, and GitLab CI/CD authentication via OIDC.

---

## Architecture

```
├── main.tf                        root wiring — calls all modules + catalog-level grants
├── provider.tf                    Databricks + AWS providers; S3 backend config
├── variables.tf                   all input variables
├── outputs.tf                     workspace URL and other outputs
├── kms.tf                         CMK for S3 bucket encryption
├── iam_ci.tf                      GitLab CI OIDC provider + IAM role
├── security.tf                    security group rules
├── terraform_state.tf             remote state config helpers
│
└── modules/
    ├── iam/                       groups, users, service principals
    ├── grants/                    Unity Catalog grants (catalog / schema / table)
    ├── compute/                   dev cluster + cluster policies
    ├── unity_catalog/             schema creation under an existing catalog
    ├── storage/                   S3 bucket + IAM role + storage credential + external location
    └── workspace/                 AWS MWS workspace provisioning (VPC, subnets, Databricks workspace)
```

### Module dependency order

```
workspace  →  iam  →  dev_compute
                   →  databricks_grants.catalog_level
                   →  s3_dev_data_bucket (via catalog storage map)

kms     →  s3_* (kms_key_arn passed in)
iam_ci  →  (independent; requires AWS + GitLab access)
```

---

## Service Principal Naming Convention

All service principals follow the pattern `sp_{env}_{team}_{scope}_{domain}`:

| Key | Generated name | Role |
|-----|---------------|------|
| `sp_dev_cdo_metastore_admin` | `sp_dev_cdo_metastore_admin` | `USE_CATALOG`, `MANAGE` on all catalogs |
| `sp_dev_cdo_workspace_admin` | `sp_dev_cdo_workspace_admin` | Workspace admin + cluster owner |
| `sp_dev_cdo_catalog_admin_<domain>` | one per domain catalog (×12) | `ALL_PRIVILEGES` on its own catalog |

`sp_dev_cdo_workspace_admin` is added to Databricks' built-in `admins` group rather than using an entitlement flag. It is also the single-user owner of the dev cluster.

---

## IAM

### Groups

| Group | Cluster create | Instance pool | SQL access |
|-------|---------------|---------------|------------|
| `GovTech Admin` | ✓ | ✓ | ✓ |
| `GovTech Service Principals` | ✓ | — | ✓ |

### Users

| User | Group |
|------|-------|
| `dheena_chandrasekar_from.persol@tech.gov.sg` | GovTech Admin |
| `TAN_Wei_Hao@tech.gov.sg` | GovTech Admin |
| `jeffrey_siew@tech.gov.sg` | GovTech Admin |
| `Germaine_TAN@tech.gov.sg` | GovTech Admin |

---

## Unity Catalog

### Domain catalogs

12 catalogs are provisioned under `local.dev_catalogs`:

`admin`, `app`, `byod`, `cybersec`, `fin`, `govn`, `hcm`, `infra`, `odc`, `ops`, `pda`, `tableau`

### Catalog grants (applied via `databricks_grants.catalog_level`)

| Principal | Privilege |
|-----------|-----------|
| `sp_dev_cdo_metastore_admin` | `USE_CATALOG`, `MANAGE` |
| `sp_dev_cdo_catalog_admin_<domain>` | `ALL_PRIVILEGES` |
| `sp_dev_cdo_workspace_admin` | `MANAGE`, `USE_CATALOG` |
| `GovTech Admin` | `ALL_PRIVILEGES` |

---

## Compute

One dev cluster (`dev_cluster`) using:
- Spark version: latest LTS (resolved dynamically via `databricks_spark_version`)
- Node type: smallest available with local disk (resolved dynamically via `databricks_node_type`)
- Autoscaling: 1–4 workers
- Auto-termination: 120 minutes
- Data security mode: `SINGLE_USER` (owner: `sp_dev_cdo_workspace_admin`)

---

## Storage (AWS)

Four S3 buckets, each with a dedicated Unity Catalog IAM role:

| Module | Purpose | UC resources | Notes |
|--------|---------|-------------|-------|
| `s3_dev_data_bucket` | Managed table storage | Storage credential + external location + all 12 catalog sub-dirs | |
| `s3_landing_data_bucket` | Raw file drop zone | Storage credential + external location | `read_only = true`, SQS file events enabled |
| `s3_autoloader_data_bucket` | Auto Loader checkpoints | Storage credential + external location | |
| `s3_workspace_data_bucket` | Workspace root (DBFS) | S3 bucket policy for Databricks root account | Scoped to `var.databricks_account_id` |

All buckets are encrypted with the shared CMK from `kms.tf`. Bucket key is enabled to reduce KMS API call costs.

### Two-pass apply for storage credentials

The Unity Catalog IAM role trust policy requires the storage credential's external ID, which is only known after the credential is created. On first apply the trust policy uses a placeholder (`"0000"`); run `terraform apply` a second time to update it with the real external ID.

---

## Workspace provisioning (`modules/workspace`)

Provisions a full Databricks MWS workspace on AWS:
- VPC with configurable CIDR, subnets, and availability zones
- Security groups and workspace network configuration
- Databricks workspace registration via the account API (`databricks.mws` provider alias)

The workspace name is `gvt_cdo_dev_internet_01`; AWS resources are prefixed `sst-gvt-sdp-databricks-dev-internet-01`.

---

## CI/CD

### Pipeline stages

| Stage | Trigger | Action |
|-------|---------|--------|
| `validate` | every push | `terraform validate` + `fmt -check` |
| `plan` | every push | `terraform plan -out=tfplan`, artifact saved for 1 week |
| `apply` | manual, `main` branch only | `terraform apply -auto-approve tfplan` |

State is stored in an S3 bucket (`sst-s3-gvt-sdp-databricks-internet-workspace`) with native S3 locking, region `ap-southeast-1`.

### AWS authentication via OIDC

The pipeline authenticates to AWS using OpenID Connect — no static access keys stored in GitLab. On each job:
1. GitLab injects a short-lived OIDC token scoped to this project
2. The token is written to `$AWS_WEB_IDENTITY_TOKEN_FILE`
3. The AWS SDK exchanges it for temporary credentials by assuming `gitlab-ci-databricks-terraform`

The OIDC provider and IAM role are provisioned by `iam_ci.tf`. This must be applied once manually before the CI pipeline can use it.

---

## Prerequisites

### Databricks
- Databricks account with Unity Catalog and MWS workspace provisioning enabled
- Account-admin service principal (`mws_client_id` / `mws_client_secret`) for the `databricks.mws` provider
- Workspace-admin service principal for resource provisioning (`DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET`)

### AWS
- IAM role with permissions to manage: S3 (`sst-s3-gvt-sdp-databricks-*`), IAM (`unity-catalog-*`, `gitlab-ci-*`), KMS (`alias/databricks-*`), VPC, EC2 networking
- See `iam_ci.tf` for the exact policy

---

## Variables

### Required

| Variable | How to set | Description |
|----------|-----------|-------------|
| `DATABRICKS_HOST` | env var | Workspace URL |
| `DATABRICKS_CLIENT_ID` | env var | Deploying SP application ID |
| `DATABRICKS_CLIENT_SECRET` | env var | Deploying SP OAuth secret |
| `service_principal_id` | `TF_VAR_*` or `terraform.tfvars` | Same value as `DATABRICKS_CLIENT_ID` |
| `databricks_account_id` | `TF_VAR_*` or `terraform.tfvars` | Databricks account UUID (required — no default) |
| `mws_client_id` | `TF_VAR_*` (sensitive) | Account-admin SP application ID for MWS provider |
| `mws_client_secret` | `TF_VAR_*` (sensitive) | Account-admin SP OAuth secret for MWS provider |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `catalog_name` | `"internet"` | Unity Catalog name for claims schemas |
| `aws_region` | `"ap-southeast-1"` | AWS region |
| `aws_account_id` | `""` | Required when applying AWS resources |
| `aws_role_arn` | `""` | IAM role to assume; leave empty to use current identity |
| `gitlab_url` | `""` | GitLab hostname (e.g. `sgts.gitlab-dedicated.com`) |
| `gitlab_project_path` | `""` | Project path for OIDC trust scoping |
| `cross_account_role_name` | `"gvt-databricks-internet-cross-account"` | Databricks cross-account EC2 IAM role name |
| `kms_key_arn` | `""` | CMK ARN from `kms.tf`; leave empty on first bootstrap apply |

### GitLab CI variables *(Settings → CI/CD → Variables)*

| Variable | Description |
|----------|-------------|
| `DATABRICKS_HOST` | Workspace URL |
| `DATABRICKS_TOKEN` | SP token or OAuth token |
| `TF_VAR_service_principal_id` | SP application ID |
| `TF_VAR_databricks_account_id` | Databricks account UUID |
| `TF_VAR_mws_client_id` | Account-admin SP application ID |
| `TF_VAR_mws_client_secret` | Account-admin SP OAuth secret |
| `GITLAB_CI_AWS_ROLE_ARN` | Output of `iam_ci.tf` — the IAM role the CI assumes |
| `TF_VAR_aws_region` | AWS region |
| `TF_VAR_aws_account_id` | AWS account ID |
| `TF_VAR_gitlab_url` | `sgts.gitlab-dedicated.com` |
| `TF_VAR_gitlab_project_path` | `dheena_chandrasekar_frompersol/databricks-terraform-test` |

> **Common pitfall:** The GitLab CI variable must be named `GITLAB_CI_AWS_ROLE_ARN` exactly.
> The pipeline YAML maps it to `AWS_ROLE_ARN` internally — if you create the variable as `AWS_ROLE_ARN`
> instead, the mapping resolves to an empty string and AWS rejects the `AssumeRoleWithWebIdentity`
> request with "Request ARN is invalid".

---

## Local Usage

### Databricks + AWS full apply

```bash
export DATABRICKS_HOST="https://<workspace>.cloud.databricks.com"
export DATABRICKS_CLIENT_ID="<sp-client-id>"
export DATABRICKS_CLIENT_SECRET="<sp-oauth-secret>"
export TF_VAR_service_principal_id="${DATABRICKS_CLIENT_ID}"
export TF_VAR_databricks_account_id="<account-uuid>"
export TF_VAR_mws_client_id="<mws-sp-client-id>"
export TF_VAR_mws_client_secret="<mws-sp-oauth-secret>"

# AWS — via IAM role assumption (or leave unset to use current identity)
export TF_VAR_aws_role_arn="arn:aws:iam::<account-id>:role/<role-name>"
export TF_VAR_aws_account_id="<aws-account-id>"

terraform init
terraform apply          # 1st apply — storage credentials use placeholder external_id
terraform apply          # 2nd apply — updates trust policy with real external_id
```

### Databricks only (no AWS access)

Target specific modules to skip AWS resources:

```bash
terraform apply \
  -target=module.iam \
  -target=module.dev_compute \
  -target=databricks_grants.catalog_level
```

---

## Planned Work

- Implement `modules/databricks_notebooks` — upload claims ETL notebooks to workspace
- Implement `modules/jobs` — two-task job (`bronze_to_silver → silver_to_gold`)
- Bootstrap OIDC (`iam_ci.tf`) once GitLab and AWS are both available
