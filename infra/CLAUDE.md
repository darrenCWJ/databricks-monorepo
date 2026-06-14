# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Local development** (requires env vars — see below):
```bash
terraform init
terraform validate
terraform fmt -recursive
terraform plan
terraform apply
terraform destroy
```

**CI/CD stages** (GitLab runner, `aws-cli-and-terraform-container:latest`):
- `validate`: `terraform validate` + `terraform fmt -check -recursive`
- `plan`: `terraform plan -out=tfplan`
- `apply`: `terraform apply -auto-approve tfplan` (manual trigger, main branch only)

**Required environment variables for local runs**:
```bash
export DATABRICKS_HOST="https://dbc-xxxxxxxx.cloud.databricks.com"
export DATABRICKS_CLIENT_ID="<sp-app-id>"
export DATABRICKS_CLIENT_SECRET="<sp-oauth-secret>"
export TF_VAR_service_principal_id="${DATABRICKS_CLIENT_ID}"
export TF_VAR_catalog_name="<catalog>"
```

## Architecture

Terraform project provisioning Databricks workspace resources using 6 child modules. The root [main.tf](main.tf) wires them together; state is stored in an S3 backend (`sst-s3-gvt-sdp-databricks-internet-workspace`, key `terraform/state/terraform.tfstate`, with `use_lockfile` for state locking) — see [provider.tf](provider.tf).

**Modules**:
1. **[modules/iam/](modules/iam/)** — groups, users, service principals, workspace roles
2. **[modules/compute/](modules/compute/)** — cluster + policy; SP from IAM is the cluster owner
3. **[modules/unity_catalog/](modules/unity_catalog/)** — medallion schemas (bronze/silver/gold) under an existing catalog; instantiated once per schema in root
4. **[modules/grants/](modules/grants/)** — UC privileges at catalog/schema/table level; 3-level conditional logic
5. **[modules/storage/](modules/storage/)** — S3 buckets; instantiated 4 times (dev-data, landing, autoloader, workspace)
6. **[modules/workspace/](modules/workspace/)** — full workspace provisioning: VPC, PrivateLink, root S3, cross-account IAM, MWS registration (see ADR-0005)

**claims_pipeline/** — Databricks Asset Bundle (DAB) for the ETL pipeline; separate from Terraform.

**Multi-workspace scaffolding**: [environments/](environments/) (dev/staging/prod) is empty but ready. [multi_workspace.yml](multi_workspace.yml) is a GitLab include template; [MULTI_WORKSPACE_GUIDE.md](MULTI_WORKSPACE_GUIDE.md) has step-by-step promotion instructions.

## Key Conventions

- **Provider**: Databricks provider pinned to `1.112.0` in [.terraform.lock.hcl](.terraform.lock.hcl). Do not bump without testing.
- **Dynamic lookups**: Cluster uses `databricks_spark_version` (DynamicLTS) and `databricks_node_type` (smallest with local disk) data sources — avoid hardcoding Spark versions or node types.
- **Grants module**: Conditional at three levels (catalog / schema / table); pass empty lists for levels not needed.
- **IAM module**: Uses `for_each` over map objects with optional fields — keep variable shapes consistent when adding new identities.
- **Hardcoded values**: `catalog_name` and `service_principal_id` are the only root variables; environment-specific values go in `environments/<env>/terraform.tfvars` when multi-workspace is enabled.
