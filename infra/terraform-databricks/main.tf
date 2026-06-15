# Minimal scaffold — add resources as you build out the workspace.

terraform {
  required_version = ">= 1.7"
  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.50"
    }
  }
  backend "s3" {
    bucket = "cdo-platform-terraform-state"
    key    = "databricks/terraform.tfstate"
    region = "ap-southeast-1"
  }
}

provider "databricks" {
  # auth via env vars in CI; profile locally
}

# Add catalogs, groups, SPs in dedicated files (catalogs.tf, groups.tf, sps.tf).
