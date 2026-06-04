terraform {
  required_version = ">= 1.10.0"

  backend "s3" {
    bucket = "sst-s3-gvt-sdp-databricks-internet-workspace"
    key    = "terraform/state/terraform.tfstate"
    region = "ap-southeast-1"
    use_lockfile = true
  }

  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
    databricks = {
      source  = "databricks/databricks"
      version = "= 1.112.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.9"
    }
  }
}

provider "databricks" {}
provider "aws" {
  region = var.aws_region

  # Optional: assume a role before making any AWS API calls.
  # Set TF_VAR_aws_role_arn to activate this — leave it empty to use
  # whatever identity is already configured (instance profile, SSO, etc.).
  dynamic "assume_role" {
    for_each = var.aws_role_arn != "" ? [1] : []
    content {
      role_arn = var.aws_role_arn
    }
  }
}

provider "databricks" {
  alias         = "mws"
  host          = "https://accounts.cloud.databricks.com"
  account_id    = var.databricks_account_id
  client_id     = var.mws_client_id
  client_secret = var.mws_client_secret
}