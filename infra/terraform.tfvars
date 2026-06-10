# Databricks provider credentials are set as environment variables, not here:
#   export DATABRICKS_HOST="https://<workspace>.cloud.databricks.com"
#   export DATABRICKS_CLIENT_ID="<sp-client-id>"
#   export DATABRICKS_CLIENT_SECRET="<sp-client-secret>"

# # Terraform variables — fill these in before applying
# service_principal_id = "53d1b3ae-d3ea-458a-a492-03a7462e7590"
# catalog_name         = "gvt_cdo_01_dev"

# # AWS + GitLab — uncomment and fill in when AWS access is granted
# aws_region            = "ap-southeast-1"
# aws_account_id        = "721140971379"
# gitlab_url            = "sgts.gitlab-dedicated.com"
# gitlab_project_path   = "dheena_chandrasekar_frompersol/databricks-terraform-test"
# databricks_account_id = "543bc187-989e-4fce-b0c7-efcefaf05f71"


# #internet workspace account
# # Terraform variables — fill these in before applying
# service_principal_id = "03eadd04-c443-42b5-9660-170c5422bda8"
# catalog_name         = "internet"

#gvt_cdo_dev_internet_01 workspace account
# Terraform variables — fill these in before applying
service_principal_id = "a5166940-52e6-450b-ab82-12d540de17e1"
catalog_name         = "system"

# AWS + GitLab — uncomment and fill in when AWS access is granted
aws_region            = "ap-southeast-1"
aws_account_id        = "721140971379"
gitlab_url            = "sgts.gitlab-dedicated.com"
gitlab_project_path   = "wog/gvt/dart/gvt-dsaid-dart/mono-dev"
databricks_account_id = "b952c76b-09ec-4f6b-a6a0-b0d5cc5a2e4f"

# Leon's Databricks account — provisions a separate workspace against the same
# cross-account role and CMKs. Listed here so their control plane passes KMS
# and IAM trust policy validation.
trusted_databricks_account_ids = ["543bc187-989e-4fce-b0c7-efcefaf05f71"]

