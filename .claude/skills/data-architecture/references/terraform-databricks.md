# Terraform + Databricks IaC Patterns

## Module decomposition

Organise infrastructure into five modules. Apply in this order — each module depends on outputs from the ones before it.

```
kms ──► storage ──────────────────────────────────────────────┐
                                                               ▼
        iam ──────────────────────────────────────────────► workspace
                                                               ▲
        unity_catalog ──► grants ──► compute ─────────────────┘
```

Apply sequence for a new workspace:
1. `kms` — CMK key + rotation policy
2. `iam` — groups, users, service principals, workspace role assignment
3. `storage` — S3 buckets + Unity Catalog external locations (requires IAM outputs)
4. `unity_catalog` — catalogs + schemas (requires storage external locations)
5. `grants` — databricks_grants resources (requires unity_catalog outputs)
6. `compute` — clusters, instance pools (requires workspace + grants)

Never merge these into one `main.tf`. The boundary between them is the natural blast radius: a grants change shouldn't touch compute config.

---

## Module: iam

Runs against the MWS (account-level) API, not the workspace API.

```hcl
resource "databricks_group" "team_groups" {
  for_each     = var.teams
  display_name = "cdo_${each.key}_${var.environment}"
}

resource "databricks_service_principal" "pipeline_sps" {
  for_each     = var.pipeline_service_principals
  display_name = "sp_${var.environment}_${each.value.team}_${each.value.purpose}_${each.value.domain}"
}

# Assign groups and SPs to the workspace
resource "databricks_mws_permission_assignment" "workspace_access" {
  for_each     = local.workspace_members
  workspace_id = var.workspace_id
  principal_id = each.value.id
  permissions  = each.value.permissions   # ["USER"] or ["ADMIN"]
}
```

**Service principal naming convention:** `sp_{env}_{team}_{purpose}_{domain}`

Examples:
- `sp_dev_cdo_metastore_admin` — account-level metastore admin
- `sp_prod_fin_pipeline_gl` — finance team's GL pipeline SP in prod
- `sp_staging_cdo_catalog_admin_hcm` — catalog admin for HCM domain in staging

Avoid generic names like `databricks-sp-1`. The name is the only human-readable identifier in audit logs.

---

## Module: storage

### S3 bucket pattern (one set per environment)

```hcl
locals {
  buckets = {
    data      = "${var.org}-databricks-${var.environment}-data"
    landing   = "${var.org}-databricks-${var.environment}-landing"
    autoloader = "${var.org}-databricks-${var.environment}-autoloader"
    workspace = "${var.org}-databricks-${var.environment}-workspace"
  }
}

resource "aws_s3_bucket" "buckets" {
  for_each = local.buckets
  bucket   = each.value
}

resource "aws_s3_bucket_server_side_encryption_configuration" "sse" {
  for_each = local.buckets
  bucket   = aws_s3_bucket.buckets[each.key].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true   # reduces KMS API calls by ~99%
  }
}
```

**Bucket purposes:**
- `data` — managed Delta table storage; one S3 prefix per catalog (e.g., `dev_fin/`, `dev_hcm/`)
- `landing` — raw file drop zone; SQS event notification enabled for Auto Loader
- `autoloader` — Auto Loader checkpoints; access via external location
- `workspace` — Databricks workspace root (DBFS); do not use for business data

### Unity Catalog external location

```hcl
resource "databricks_storage_credential" "main" {
  name = "uc-storage-cred-${var.environment}"
  aws_iam_role {
    role_arn = aws_iam_role.databricks_cross_account.arn
  }
}

resource "databricks_external_location" "data" {
  name            = "data-${var.environment}"
  url             = "s3://${aws_s3_bucket.buckets["data"].id}"
  credential_name = databricks_storage_credential.main.id
}
```

**Two-pass apply pattern for storage credentials:**
The Databricks cross-account IAM role trust policy requires the external ID that Unity Catalog generates, but that ID doesn't exist until after the first apply. Work around this with:

1. First apply: use placeholder `"0000"` as the external ID in the trust policy condition.
2. After apply: read the real external ID from `databricks_storage_credential.main.aws_iam_role[0].external_id`.
3. Update the IAM trust policy with the real external ID via a `null_resource` + `aws_iam_role_policy` update.
4. Second apply: everything validates correctly.

---

## Module: unity_catalog

One module instantiation per domain catalog:

```hcl
module "fin_catalog" {
  source      = "./modules/unity_catalog"
  catalog     = "fin"
  environment = var.environment
  metastore_id = var.metastore_id
}

# In modules/unity_catalog/main.tf:
resource "databricks_catalog" "main" {
  name         = "${var.environment}_${var.catalog}"
  metastore_id = var.metastore_id
  storage_root = "s3://${var.data_bucket}/${var.environment}_${var.catalog}"
}

resource "databricks_schema" "layers" {
  for_each     = toset(["bronze", "silver", "gold"])
  catalog_name = databricks_catalog.main.name
  name         = each.key
}
```

Never create schemas on-the-fly from application code. Schema creation is an infrastructure act — it must go through Terraform + code review.

---

## Module: grants

Keep grants as a separate module so they can evolve independently of schema topology.

```hcl
resource "databricks_grants" "catalog_level" {
  catalog = "${var.environment}_${var.catalog}"
  grant {
    principal  = "cdo_${var.team}_${var.environment}"
    privileges = ["USE_CATALOG"]
  }
}

resource "databricks_grants" "silver_read" {
  schema = "${var.environment}_${var.catalog}.silver"
  grant {
    principal  = "cdo_${var.team}_${var.environment}"
    privileges = ["SELECT", "USE_SCHEMA"]
  }
}

resource "databricks_grants" "bronze_write" {
  schema = "${var.environment}_${var.catalog}.bronze"
  grant {
    principal  = databricks_service_principal.pipeline_sps["${var.team}_pipeline"].application_id
    privileges = ["SELECT", "MODIFY", "CREATE_TABLE", "USE_SCHEMA"]
  }
}
```

Principle: **humans (groups) get SELECT; service principals get MODIFY**. Never grant MODIFY to a human group. MANAGE at the catalog level is reserved for the catalog admin SP only.

---

## State backend

One state file per environment per stack prevents blast radius from crossing environments.

```hcl
# environments/prod/backend.tf
terraform {
  backend "s3" {
    bucket         = "your-org-tfstate"
    key            = "databricks/prod/workspace.tfstate"
    region         = "ap-southeast-1"
    encrypt        = true
    kms_key_id     = "arn:aws:kms:ap-southeast-1:123456789:key/abc..."
  }
}
```

Directory structure that works well for multi-environment:

```
infra/
├── modules/
│   ├── iam/
│   ├── storage/
│   ├── unity_catalog/
│   ├── grants/
│   └── compute/
├── environments/
│   ├── dev/
│   │   ├── main.tf          # instantiates modules with dev vars
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   ├── staging/
│   └── prod/
└── shared/
    └── kms.tf               # CMK shared across environments (or per-env)
```

---

## GitLab OIDC CI (no static keys)

Authenticate CI to AWS without storing access keys:

```yaml
# .gitlab-ci.yml
variables:
  AWS_ROLE_ARN: "arn:aws:iam::123456789:role/gitlab-ci-terraform"
  AWS_DEFAULT_REGION: "ap-southeast-1"

.terraform_base:
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: "https://gitlab.com"
  before_script:
    - |
      export $(printf "AWS_ACCESS_KEY_ID=%s AWS_SECRET_ACCESS_KEY=%s AWS_SESSION_TOKEN=%s"
        $(aws sts assume-role-with-web-identity
          --role-arn "$AWS_ROLE_ARN"
          --role-session-name "gitlab-ci-$CI_PIPELINE_ID"
          --web-identity-token "$GITLAB_OIDC_TOKEN"
          --query "Credentials.[AccessKeyId,SecretAccessKey,SessionToken]"
          --output text))
```

The IAM trust policy on the GitLab CI role:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::123456789:oidc-provider/gitlab.com" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringLike": {
        "gitlab.com:sub": "project_path:your-org/your-repo:ref_type:branch:ref:*"
      }
    }
  }]
}
```

Scope the condition to your specific project path. Don't allow `*` for the sub claim — that permits any project in your org.

---

## Multi-workspace tenant provisioning

When provisioning workspaces for multiple teams or agencies (e.g., a shared data platform), use per-workspace state:

```
environments/
├── dev/
│   ├── agency-a/
│   │   ├── terraform.tfvars      # agency-specific vars
│   │   └── backend.s3.tfbackend  # isolated state
│   └── agency-b/
│       ├── terraform.tfvars
│       └── backend.s3.tfbackend
└── prod/
    ├── agency-a/
    └── agency-b/
```

Generate configs with a script to avoid copy-paste drift:

```bash
./scripts/generate-workspace-config.sh \
  --environment dev \
  --agency agency-a \
  --region ap-southeast-1 \
  --account-id 123456789
```

Apply a specific workspace:

```bash
./scripts/tf.sh plan dev dbx-serverless agency-a
./scripts/tf.sh apply dev dbx-serverless agency-a
```

The `tf.sh` wrapper sets `TF_WORKSPACE` and selects the right backend config automatically.

---

## CI/CD pipeline stages

```yaml
stages:
  - validate
  - plan
  - apply

validate:
  script:
    - terraform validate
    - terraform fmt -check -recursive

plan:
  script:
    - terraform plan -out=tfplan -var-file="environments/${ENV}/terraform.tfvars"
  artifacts:
    paths: [tfplan]
    expire_in: 1 week

apply:
  script:
    - terraform apply -auto-approve tfplan
  when: manual       # always manual for prod; can auto for dev
  only:
    - main           # never apply from feature branches
```

The `plan` artifact is required for the `apply` step so that what you reviewed in `plan` is exactly what `apply` executes. Never run `terraform apply` without a plan file in CI.
