#!/usr/bin/env bash
# Imports all pre-existing resources into the fresh Terraform state.
# Run from the project root with valid AWS and Databricks credentials.
set -euo pipefail

AWS_ACCOUNT_ID="721140971379"
REGION="ap-southeast-1"
GITLAB_URL="sgts.gitlab-dedicated.com"
CATALOG_NAME="internet"

# Fetch state list once — fail fast if credentials are invalid.
echo "Fetching current state list..."
STATE_LIST=$(terraform state list)

# ── skip if already in state ──────────────────────────────────────────────────
tf_import() {
  local addr="$1"
  local id="$2"
  if echo "$STATE_LIST" | grep -qF "$addr"; then
    echo "  SKIP (already in state): $addr"
  else
    echo "  importing: $addr  (id=$id)"
    terraform import "$addr" "$id"
  fi
}

# ── KMS ───────────────────────────────────────────────────────────────────────
echo ""
echo "=== KMS ==="

# The original key (alias/sdp-databricks-s3-dev) is now tracked as storage_cmk.
# The moved block in kms.tf handles the rename in state automatically on plan/apply,
# so this import targets the new resource address directly.
KEY_ID=$(aws kms describe-key --key-id alias/sdp-databricks-s3-dev \
  --query 'KeyMetadata.KeyId' --output text)

# If a different key landed in state during a failed apply, swap it out.
if echo "$STATE_LIST" | grep -qF "aws_kms_key.storage_cmk"; then
  STATE_KEY=$(terraform state pull | \
    python3 -c "import json,sys; s=json.load(sys.stdin); r=[r for r in s['resources'] if r['type']=='aws_kms_key' and r['name']=='storage_cmk']; print(r[0]['instances'][0]['attributes']['key_id']) if r else print('')")
  if [ -n "$STATE_KEY" ] && [ "$STATE_KEY" != "$KEY_ID" ]; then
    echo "  removing wrong KMS key from state ($STATE_KEY)"
    terraform state rm aws_kms_key.storage_cmk
  fi
fi

tf_import aws_kms_key.storage_cmk   "$KEY_ID"
tf_import aws_kms_alias.storage_cmk "alias/sdp-databricks-s3-dev"

# ── GitLab CI OIDC / IAM ──────────────────────────────────────────────────────
echo ""
echo "=== GitLab CI OIDC / IAM ==="

OIDC_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/${GITLAB_URL}"
CI_POLICY_ARN=$(aws iam list-policies --scope Local \
  --query "Policies[?PolicyName=='gitlab-ci-databricks-terraform'].Arn" \
  --output text)
CI_ROLE_NAME="gitlab-ci-databricks-terraform"

tf_import aws_iam_openid_connect_provider.gitlab          "$OIDC_ARN"
tf_import aws_iam_policy.gitlab_ci_terraform              "$CI_POLICY_ARN"
tf_import aws_iam_role.gitlab_ci                          "$CI_ROLE_NAME"
tf_import aws_iam_role_policy_attachment.gitlab_ci_terraform \
  "${CI_ROLE_NAME}/${CI_POLICY_ARN}"

# ── S3 state bucket ───────────────────────────────────────────────────────────
echo ""
echo "=== Terraform state S3 bucket ==="

tf_import aws_s3_bucket.terraform_state \
  "sst-s3-gvt-sdp-databricks-internet-workspace"
tf_import aws_s3_bucket_versioning.terraform_state \
  "sst-s3-gvt-sdp-databricks-internet-workspace"
tf_import aws_s3_bucket_server_side_encryption_configuration.terraform_state \
  "sst-s3-gvt-sdp-databricks-internet-workspace"
tf_import aws_s3_bucket_public_access_block.terraform_state \
  "sst-s3-gvt-sdp-databricks-internet-workspace"

# ── Storage module helper ─────────────────────────────────────────────────────
# $1 = module name  $2 = bucket name  $3 = role name  $4 = purpose (for file_events check)
import_storage_module() {
  local mod="$1"
  local bucket="$2"
  local role="$3"
  local purpose="$4"

  local policy_arn
  policy_arn=$(aws iam list-policies --scope Local \
    --query "Policies[?PolicyName=='${role}-s3-access'].Arn" \
    --output text)

  tf_import "module.${mod}.aws_s3_bucket.sdp_s3_bucket"              "$bucket"
  tf_import "module.${mod}.aws_s3_bucket_server_side_encryption_configuration.this[0]" "$bucket"
  tf_import "module.${mod}.aws_iam_role.unity_catalog"               "$role"
  tf_import "module.${mod}.aws_iam_policy.s3_access"                 "$policy_arn"
  tf_import "module.${mod}.aws_iam_role_policy_attachment.s3_access" \
    "${role}/${policy_arn}"

  if [ "$purpose" = "landing" ]; then
    local fe_policy_arn
    fe_policy_arn=$(aws iam list-policies --scope Local \
      --query "Policies[?PolicyName=='${role}-file-events'].Arn" \
      --output text)
    tf_import "module.${mod}.aws_iam_policy.file_events[0]"                        "$fe_policy_arn"
    tf_import "module.${mod}.aws_iam_role_policy_attachment.file_events[0]"        \
      "${role}/${fe_policy_arn}"
  fi

  if [ "$purpose" = "workspace" ]; then
    tf_import "module.${mod}.aws_s3_bucket_policy.workspace[0]" "$bucket"
  fi
}

echo ""
echo "=== S3 data buckets + IAM roles/policies ==="

import_storage_module "s3_dev_data_bucket"       "sst-s3-gvt-sdp-databricks-dev-data"       "unity-catalog-dev-data"       "data"
import_storage_module "s3_landing_data_bucket"   "sst-s3-gvt-sdp-databricks-dev-landing"    "unity-catalog-dev-landing"    "landing"
import_storage_module "s3_autoloader_data_bucket" "sst-s3-gvt-sdp-databricks-dev-autoloader" "unity-catalog-dev-autoloader" "autoloader"
import_storage_module "s3_workspace_data_bucket" "sst-s3-gvt-sdp-databricks-dev-workspace"  "unity-catalog-dev-workspace"  "workspace"

# ── Databricks storage credentials ───────────────────────────────────────────
echo ""
echo "=== Databricks storage credentials ==="

for cred in dev-data-cred dev-landing-cred dev-autoloader-cred; do
  case $cred in
    dev-data-cred)       mod_path="module.s3_dev_data_bucket.databricks_storage_credential.this[0]" ;;
    dev-landing-cred)    mod_path="module.s3_landing_data_bucket.databricks_storage_credential.this[0]" ;;
    dev-autoloader-cred) mod_path="module.s3_autoloader_data_bucket.databricks_storage_credential.this[0]" ;;
  esac
  tf_import "$mod_path" "$cred"
done

# ── Databricks external locations ─────────────────────────────────────────────
echo ""
echo "=== Databricks external locations ==="

for loc in dev-data-location dev-landing-location dev-autoloader-location; do
  case $loc in
    dev-data-location)       mod_path="module.s3_dev_data_bucket.databricks_external_location.this[0]" ;;
    dev-landing-location)    mod_path="module.s3_landing_data_bucket.databricks_external_location.this[0]" ;;
    dev-autoloader-location) mod_path="module.s3_autoloader_data_bucket.databricks_external_location.this[0]" ;;
  esac
  tf_import "$mod_path" "$loc"
done

# ── helper: SCIM API via curl using Terraform env vars ────────────────────────
scim_get() {
  local path="$1"
  curl -s -X GET \
    -H "Authorization: Bearer $(curl -s -X POST \
      "${DATABRICKS_HOST}/oidc/v1/token" \
      -u "${DATABRICKS_CLIENT_ID}:${DATABRICKS_CLIENT_SECRET}" \
      -d "grant_type=client_credentials&scope=all-apis" | jq -r '.access_token')" \
    "${DATABRICKS_HOST}/api/2.0/preview/scim/v2/${path}"
}

# ── Databricks groups ─────────────────────────────────────────────────────────
echo ""
echo "=== Databricks groups ==="

GROUPS_JSON=$(scim_get "Groups?count=200")
GOVTECH_ADMIN_ID=$(echo "$GROUPS_JSON" | jq -r '.Resources[] | select(.displayName == "GovTech Admin") | .id')
GOVTECH_SPS_ID=$(echo  "$GROUPS_JSON" | jq -r '.Resources[] | select(.displayName == "GovTech Service Principals") | .id')

tf_import 'module.iam.databricks_group.groups["govtech_admin"]' "$GOVTECH_ADMIN_ID"
tf_import 'module.iam.databricks_group.groups["govtech_sps"]'   "$GOVTECH_SPS_ID"

# ── Databricks users ──────────────────────────────────────────────────────────
echo ""
echo "=== Databricks users ==="

USERS_JSON=$(scim_get "Users?count=200")

import_user() {
  local key="$1"
  local email="$2"
  local user_id
  user_id=$(echo "$USERS_JSON" | \
    jq -r --arg e "$email" '.Resources[] | select(.userName | ascii_downcase == ($e | ascii_downcase)) | .id')
  if [ -z "$user_id" ]; then
    echo "  WARN: user not found: $email"
    return
  fi
  tf_import "module.iam.databricks_user.users[\"${key}\"]" "$user_id"
}

import_user dheena   "dheena_chandrasekar_from.persol@tech.gov.sg"
import_user wei_hao  "TAN_Wei_Hao@tech.gov.sg"
import_user jeffrey  "jeffrey_siew@tech.gov.sg"
import_user germaine "Germaine_TAN@tech.gov.sg"

# ── Databricks service principals ─────────────────────────────────────────────
echo ""
echo "=== Databricks service principals ==="

SPS_JSON=$(scim_get "ServicePrincipals?count=200")

import_sp() {
  local key="$1"
  local display_name="$2"
  local app_id
  app_id=$(echo "$SPS_JSON" | \
    jq -r --arg n "$display_name" '.Resources[] | select(.displayName == $n) | .applicationId')
  if [ -z "$app_id" ]; then
    echo "  WARN: SP not found: $display_name"
    return
  fi
  tf_import "module.iam.databricks_service_principal.sps[\"${key}\"]" "$app_id"
}

import_sp "dev_cdo_ms_admin" "sp_dev_cdo_metastore_admin"
import_sp "dev_cdo_ws_admin" "sp_dev_cdo_workspace_admin"

for domain in admin app byod cybersec fin govn hcm infra odc ops pda tableau; do
  import_sp "sp_dev_cdo_catalog_${domain}" "sp_dev_cdo_catalog_${domain}"
done

# ── Databricks schemas ────────────────────────────────────────────────────────
echo ""
echo "=== Databricks schemas ==="

tf_import module.bronze_schema.databricks_schema.schema "${CATALOG_NAME}.claims_bronze"
tf_import module.silver_schema.databricks_schema.schema "${CATALOG_NAME}.claims_silver"
tf_import module.gold_schema.databricks_schema.schema   "${CATALOG_NAME}.claims_gold"

echo ""
echo "All imports complete. Run 'terraform plan' to review remaining diffs."
