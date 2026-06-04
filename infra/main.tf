# Look up the pre-existing Databricks cross-account IAM role (EC2 provisioning).
# This role is not managed here — it was created at workspace setup time.
# Uses the plural form so plan/apply succeeds even if the role is absent.
data "aws_iam_roles" "cross_account" {
  name_regex = "^${var.cross_account_role_name}$"
}

#for creating classic compute for dev environment
module "dev_compute" {
  source                  = "./modules/compute"
  cluster_name            = "dev_cluster"
  autotermination_minutes = 120
  single_user_name        = module.iam.service_principal_application_ids["sp_dev_cdo_workspace_admin"]
}

locals {
  dev_catalogs = {
    admin    = { name_env = "dev", name_team = "cdo", name_scope = "catalog", name_domain = "admin" }
    app      = { name_env = "dev", name_team = "cdo", name_scope = "catalog", name_domain = "app" }
    byod     = { name_env = "dev", name_team = "cdo", name_scope = "catalog", name_domain = "byod" }
    cybersec = { name_env = "dev", name_team = "cdo", name_scope = "catalog", name_domain = "cybersec" }
    fin      = { name_env = "dev", name_team = "cdo", name_scope = "catalog", name_domain = "fin" }
    govn     = { name_env = "dev", name_team = "cdo", name_scope = "catalog", name_domain = "govn" }
    hcm      = { name_env = "dev", name_team = "cdo", name_scope = "catalog", name_domain = "hcm" }
    infra    = { name_env = "dev", name_team = "cdo", name_scope = "catalog", name_domain = "infra" }
    odc      = { name_env = "dev", name_team = "cdo", name_scope = "catalog", name_domain = "odc" }
    ops      = { name_env = "dev", name_team = "cdo", name_scope = "catalog", name_domain = "ops" }
    pda      = { name_env = "dev", name_team = "cdo", name_scope = "catalog", name_domain = "pda" }
    tableau  = { name_env = "dev", name_team = "cdo", name_scope = "catalog", name_domain = "tableau" }
  }

  # map of catalog_name => { subdir, owner } passed to the storage module
  # owner is set after module.iam is known; catalogs depend on module.iam via depends_on
  dev_catalog_storage = {
    for k, v in local.dev_catalogs :
    "${v.name_domain}_${v.name_env}" => {
      subdir = v.name_domain
      owner  = module.iam.service_principal_application_ids["sp_${v.name_env}_${v.name_team}_catalog_admin_${v.name_domain}"]
    }
  }

  dev_catalog_sps = {
    for k, v in local.dev_catalogs :
    "sp_${v.name_env}_${v.name_team}_catalog_admin_${v.name_domain}" => {
      display_name = "sp_${v.name_env}_${v.name_team}_catalog_admin_${v.name_domain}"
      groups       = ["govtech_sps"]
    }
  }
}

#creation of IAM policy/objects in Databricks
module "iam" {
  source    = "./modules/iam"
  providers = { databricks.mws = databricks.mws }

  workspace_id = module.workspace.workspace_id

  groups = {
    govtech_admin = {
      display_name               = "GovTech Admin"
      allow_cluster_create       = true #create clusters
      allow_instance_pool_create = true #create instance pools
      workspace_access           = true #access to the workspace UI
      databricks_sql_access      = true
      is_workspace_admin         = true
    }

    govtech_sps = {
      display_name               = "GovTech Service Principals"
      allow_cluster_create       = true
      allow_instance_pool_create = false
      workspace_access           = false
      databricks_sql_access      = true
    }
  }

  users = {
    dheena = {
      user_name = "dheena_chandrasekar_from.persol@tech.gov.sg"
      groups    = ["govtech_admin"]
    }
    wei_hao = {
      user_name = "TAN_Wei_Hao@tech.gov.sg"
      groups    = ["govtech_admin"]
    }
    jeffrey = {
      user_name = "jeffrey_siew@tech.gov.sg"
      groups    = ["govtech_admin"]
    }
    germaine = {
      user_name = "Germaine_TAN@tech.gov.sg"
      groups    = ["govtech_admin"]
    }
  }

  service_principals = merge(
    {
      # db_sp = {
      #   application_id       = var.service_principal_id
      #   display_name         = "svc-prc-1"
      #   groups               = ["govtech_sps"]
      #   is_workspace_admin   = true
      #   allow_cluster_create = true
      # }

      sp_dev_cdo_metastore_admin = {
        display_name = "sp_dev_cdo_metastore_admin"
        groups       = ["govtech_sps"]
      }

      sp_dev_cdo_workspace_admin = {
        display_name               = "sp_dev_cdo_workspace_admin"
        is_workspace_admin         = true
        allow_cluster_create       = true
        allow_instance_pool_create = true
      }
    },
    local.dev_catalog_sps
  )
}

# catalog-level grants: metastore admin SP gets MANAGE, each catalog SP gets ALL_PRIVILEGES on its own catalog
resource "databricks_grants" "catalog_level" {
  for_each = local.dev_catalog_storage

  catalog = each.key

  grant {
    principal  = module.iam.service_principal_application_ids["sp_dev_cdo_metastore_admin"]
    privileges = ["USE_CATALOG", "MANAGE"]
  }

  grant {
    principal  = module.iam.service_principal_application_ids["sp_dev_cdo_catalog_admin_${split("_", each.key)[0]}"]
    privileges = ["ALL_PRIVILEGES"]
  }

  # Terraform CI/CD SP needs USE CATALOG to read catalog state after ownership transfer
  grant {
    principal  = module.iam.service_principal_application_ids["sp_dev_cdo_workspace_admin"]
    privileges = ["MANAGE", "USE_CATALOG"]
  }

  grant {
    principal  = module.iam.group_names["govtech_admin"]
    privileges = ["ALL_PRIVILEGES"]
  }

  depends_on = [module.iam, module.s3_dev_data_bucket]
}



#creation of s3 buckets
module "s3_dev_data_bucket" {
  source = "./modules/storage"

  env            = "dev"
  purpose        = "data"
  aws_account_id = var.aws_account_id
  iam_role_name  = "unity-catalog-dev-data"

  storage_credential_name = "dev-data-cred"
  external_location_name  = "dev-data-location"
  catalogs                = local.dev_catalog_storage
  enable_kms              = true
  kms_key_arn             = aws_kms_key.s3.arn
  external_location_grants = {
    "GovTech Admin" = ["READ_FILES", "WRITE_FILES", "MANAGE"]
  }
}

module "s3_landing_data_bucket" {
  source = "./modules/storage"

  env            = "dev"
  purpose        = "landing"
  aws_account_id = var.aws_account_id
  iam_role_name  = "unity-catalog-dev-landing"

  storage_credential_name = "dev-landing-cred"
  external_location_name  = "dev-landing-location"
  enable_file_events      = true
  read_only               = true
  enable_kms              = true
  kms_key_arn             = aws_kms_key.s3.arn
  external_location_grants = {
    "GovTech Admin" = ["READ_FILES", "MANAGE"]
  }
}

module "s3_autoloader_data_bucket" {
  source = "./modules/storage"

  env            = "dev"
  purpose        = "autoloader"
  aws_account_id = var.aws_account_id
  iam_role_name  = "unity-catalog-dev-autoloader"

  storage_credential_name = "dev-autoloader-cred"
  external_location_name  = "dev-autoloader-location"
  enable_kms              = true
  kms_key_arn             = aws_kms_key.s3.arn
  external_location_grants = {
    "GovTech Admin" = ["READ_FILES", "WRITE_FILES", "MANAGE"]
  }
}

module "s3_workspace_data_bucket" {
  source = "./modules/storage"

  env                   = "dev"
  purpose               = "workspace"
  aws_account_id        = var.aws_account_id
  iam_role_name         = "unity-catalog-dev-workspace"
  databricks_account_id = var.databricks_account_id
  enable_kms            = true
  kms_key_arn           = aws_kms_key.s3.arn
}


resource "databricks_grants" "dev_data_cred" {
  storage_credential = "dev-data-cred"
  grant {
    principal  = module.iam.group_names["govtech_admin"]
    privileges = ["CREATE_EXTERNAL_LOCATION"]
  }
}

resource "databricks_grants" "dev_landing_cred" {
  storage_credential = "dev-landing-cred"
  grant {
    principal  = module.iam.group_names["govtech_admin"]
    privileges = ["CREATE_EXTERNAL_LOCATION"]
  }
}

resource "databricks_grants" "dev_autoloader_cred" {
  storage_credential = "dev-autoloader-cred"
  grant {
    principal  = module.iam.group_names["govtech_admin"]
    privileges = ["CREATE_EXTERNAL_LOCATION"]
  }
}

# ── Databricks workspace provisioning ─────────────────────────────────────────
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

output "internet_workspace_url" {
  description = "URL of the internet workspace"
  value       = module.workspace.workspace_url
}
