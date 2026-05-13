# Bootstrap: CI authentication + audit-log bucket

One-time platform-team setup. Run once per environment (dev / staging / prod).
Expected to take ~1 hour per environment.

## Part 1 — GitLab → Databricks authentication (direction A)

This is what `databricks bundle deploy` uses in CI.

### Step 1.1 — Create a service principal in Databricks

1. Log in to the Databricks **dev** workspace as an account admin.
2. Workspace → Settings → Identity and Access → Service Principals → **Add Service Principal**.
3. Name it `cdo_ci_${env}` (e.g. `cdo_ci_dev`). Skip "Workspace admin" — grant least-privilege below.
4. Grant the SP:
   - **Workspace access** (Can use)
   - **Catalog `cdo_${env}` MANAGE** grant (so it can deploy bundles)
   - **CREATE_TABLE / CREATE_VOLUME** in target schemas as needed
5. Repeat for staging and prod workspaces.

### Step 1.2 — Generate an OAuth M2M secret for the SP

(Tokens are cleaner than PATs for service principals.)

1. Account Console → Service Principals → click `cdo_ci_${env}`.
2. **Generate Secret**. Copy the `client_id` and `client_secret` immediately — the secret is shown once.
3. Default lifetime is 1 year; cadence below.

### Step 1.3 — Store secrets in GitLab

GitLab → Project → Settings → CI/CD → Variables. Add per environment (scope = the matching protected env):

| Variable | Value | Scope | Protected | Masked |
|---|---|---|---|---|
| `DATABRICKS_HOST` | `https://dev-cdo.gcc.databricks.com` (and staging/prod URLs) | env-scoped | ✓ | ✗ |
| `DATABRICKS_CLIENT_ID` | from Step 1.2 | env-scoped | ✓ | ✓ |
| `DATABRICKS_CLIENT_SECRET` | from Step 1.2 | env-scoped | ✓ | ✓ |

The `databricks` CLI auto-picks these env vars (OAuth M2M).

> **Why not personal access tokens?** PATs are tied to a human account; if that person leaves you lose CI. Service-principal OAuth has no such bus factor.

### Step 1.4 — Rotation

- **Cadence:** every 90 days, plus immediately on any suspected leak.
- **Process:** generate new secret in Databricks, paste into GitLab variable, **then** delete the old secret. CI will use the new one on next pipeline.
- **Document:** add a calendar reminder to `@cdo/platform-team`.

### Step 1.5 — Future: migrate to OIDC

Long-lived secrets are an IM8 risk surface. When you have bandwidth:

- GitLab issues an OIDC token per pipeline.
- AWS IAM role configured to trust GitLab's OIDC provider, scoped to specific projects + protected branches.
- That role assumes a Databricks SP role via Databricks-managed federation.
- No long-lived secrets in GitLab at all.

This is a 1–2 day project. Add it to the Tier 1 TODO list when it's prioritised.

## Part 2 — Databricks → GitLab (direction B, optional)

Only needed if engineers want to use Databricks Repos / Git Folders to edit
notebooks directly in the workspace (the alternative is editing on their
laptop and pushing via GitLab).

### Step 2.1 — Create a GitLab Personal Access Token

(Must be a real human's PAT for now — GitLab doesn't issue group-level Git read-write tokens cleanly.)

1. GitLab → User Settings → Access Tokens.
2. Name: `databricks-${user}-${env}`. Scopes: `read_repository`, `write_repository`. Expiry: 90 days.
3. Copy the token.

### Step 2.2 — Register in Databricks

1. Databricks workspace → User Settings → Linked accounts → **Git provider: GitLab**.
2. Paste the token + your GitLab username.
3. The user can now clone the repo into a Databricks Git Folder.

### Step 2.3 — Rotation

Same 90-day cadence. When a user leaves, revoke their PAT immediately and
delete the corresponding Databricks linked-account entry.

## Part 3 — Audit-log bucket

The platform-team owns this. One bucket per env (or one shared bucket with
prefix per env).

### Step 3.1 — Create the bucket via Terraform

Add to `infra/terraform-databricks/main.tf` (or a new `infra/audit/main.tf`):

```hcl
resource "aws_s3_bucket" "audit" {
  bucket = "cdo-soc2-audit-${var.environment}"
}

resource "aws_s3_bucket_versioning" "audit" {
  bucket = aws_s3_bucket.audit.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_object_lock_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    default_retention {
      mode = "GOVERNANCE"
      years = 7
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.kms_key_arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "audit" {
  bucket                  = aws_s3_bucket.audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

### Step 3.2 — Grant CI write-only access

Service principal `cdo_ci_${env}` needs **PutObject** + **GetBucketLocation**
only — no Delete, no Get on existing objects. This makes the bucket
genuinely append-only from CI.

### Step 3.3 — Test

Trigger a no-op deploy to dev and verify the audit record appears:

```bash
aws s3 ls s3://cdo-soc2-audit-dev/dev/$(date +%F)/ --profile gcc-dev
```

### Step 3.4 — SIEM forwarder (future TODO)

Out of scope today. Plan: Kinesis Firehose subscribed to bucket events,
delivering to the agency SIEM when one is chosen.

## Quick reference — what's running where

| What | Where it lives |
|---|---|
| Databricks SP secret (OAuth M2M) | GitLab CI/CD variables, env-scoped + masked + protected |
| GitLab PAT (per engineer, for Repos feature) | Each user's Databricks workspace settings |
| Audit bucket | AWS GCC account, region `ap-southeast-1`, Object Lock 7y |
| Audit record format | `s3://cdo-soc2-audit-${env}/${target}/${date}/${bundle}-${sha[:12]}.json` |
