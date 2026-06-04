terraform {
  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.0"
    }
  }
}

data "databricks_spark_version" "latest_lts" {
  long_term_support = var.long_term_support
}

data "databricks_node_type" "smallest" {
  local_disk = true
}

resource "databricks_cluster" "cluster" {
  cluster_name            = var.cluster_name
  spark_version           = data.databricks_spark_version.latest_lts.id
  node_type_id            = data.databricks_node_type.smallest.id
  autotermination_minutes = var.autotermination_minutes
  data_security_mode      = "SINGLE_USER"
  single_user_name        = var.single_user_name
  policy_id               = databricks_cluster_policy.dev_policy.id

  autoscale {
    min_workers = 1
    max_workers = 4
  }
}

#databricks cluster policy
resource "databricks_cluster_policy" "dev_policy" {
  name = "${var.cluster_name}_policy"
  definition = jsonencode({
    "autotermination_minutes" : {
      "type" : "fixed",
      "value" : var.autotermination_minutes
    },
    "autoscale.min_workers" : {
      "type" : "fixed",
      "value" : 1
    },
    "autoscale.max_workers" : {
      "type" : "range",
      "maxValue" : 4
    },
    "data_security_mode" : {
      "type" : "fixed",
      "value" : "SINGLE_USER"
    }
  })
}

#compute policy for job computes

#job compute (small)
resource "databricks_cluster_policy" "job_compute_small_with_iam" {
  name             = "Job Compute (Small) with IAM"
  description      = "Fast setup for development testing and initial validation\nNode_type selection \nm7i - default all purpose compute - good for Small to mid-size databases. \nc7i - when more compute is needed and less on how much data to hold - Batch processing or Scientific modeling\nr7i - when there are data overflow when processing the files. - Reading in large files of data"
  policy_family_id = "job-cluster"
  policy_family_definition_overrides = jsonencode({
    spark_version = {
      type         = "allowlist"
      values       = ["15.4.x-scala2.12", "16.4.x-scala2.13", "17.3.x-scala2.13"]
      defaultValue = "15.4.x-scala2.12"
    }
    node_type_id = {
      type         = "allowlist"
      values       = ["m7i.large", "c7i.xlarge"]
      defaultValue = "m7i.large"
    }
    num_workers = {
      type         = "range"
      defaultValue = 1
      maxValue     = 2
      isOptional   = true
    }
    "autoscale.max_workers" = {
      type         = "range"
      defaultValue = 2
      maxValue     = 4
      isOptional   = true
    }
    "autoscale.min_workers" = {
      type         = "range"
      defaultValue = 1
      maxValue     = 2
      isOptional   = true
    }
    driver_node_type_id = {
      type         = "allowlist"
      values       = ["m7i.large"]
      defaultValue = "m7i.large"
      isOptional   = true
    }
    runtime_engine = {
      type   = "fixed"
      value  = "STANDARD"
      hidden = true
    }
    data_security_mode = {
      type  = "fixed"
      value = "SINGLE_USER"
    }
    "custom_tags.COMPUTE_USERS" = {
      type  = "fixed"
      value = "STANDARD"
    }
    "custom_tags.TYPE_OF_TASK" = {
      type  = "fixed"
      value = "job_small"
    }
  })
}


#job compute (medium)
resource "databricks_cluster_policy" "job_compute_medium_with_iam" {
  name             = "Job Compute (Medium) with IAM"
  description      = "General-purpose for running non-interactive workloads.\nNode_type selection \nm7i - default all purpose compute - good for Small to mid-size databases. \nc7i - when more compute is needed and less on how much data to hold - Batch processing or Scientific modeling \nr7i - when there are data overflow when processing the files. - Reading in large files of data"
  policy_family_id = "job-cluster"
  policy_family_definition_overrides = jsonencode({
    spark_version = {
      type         = "allowlist"
      values       = ["15.4.x-scala2.12", "16.4.x-scala2.13", "17.3.x-scala2.13"]
      defaultValue = "15.4.x-scala2.12"
    }
    node_type_id = {
      type         = "allowlist"
      values       = ["m7i.xlarge", "c7i.2xlarge", "r7i.xlarge"]
      defaultValue = "m7i.xlarge"
    }
    num_workers = {
      type         = "range"
      defaultValue = 1
      maxValue     = 2
      isOptional   = true
    }
    "autoscale.max_workers" = {
      type         = "range"
      defaultValue = 2
      maxValue     = 4
      isOptional   = true
    }
    "autoscale.min_workers" = {
      type         = "range"
      defaultValue = 1
      maxValue     = 2
      isOptional   = true
    }
    driver_node_type_id = {
      type         = "allowlist"
      values       = ["r7i.xlarge", "m7i.xlarge", "c7i.2xlarge"]
      defaultValue = "m7i.xlarge"
      isOptional   = true
    }
    runtime_engine = {
      type   = "fixed"
      value  = "STANDARD"
      hidden = true
    }
    data_security_mode = {
      type  = "fixed"
      value = "SINGLE_USER"
    }
    "custom_tags.COMPUTE_USERS" = {
      type  = "fixed"
      value = "STANDARD"
    }
    "custom_tags.TYPE_OF_TASK" = {
      type  = "fixed"
      value = "job_medium"
    }
  })
}

# #job compute (large)
resource "databricks_cluster_policy" "job_compute_large_with_iam" {
  name             = "Job Compute (Large) with IAM"
  description      = "General-purpose for running non-interactive workloads.\nNode_type selection \nm7i - default all purpose compute - good for Small to mid-size databases. \nc7i - when more compute is needed and less on how much data to hold - Batch processing or Scientific modeling \nr7i - when there are data overflow when processing the files. - Reading in large files of data"
  policy_family_id = "job-cluster"
  policy_family_definition_overrides = jsonencode({
    spark_version = {
      type         = "allowlist"
      values       = ["15.4.x-scala2.12", "16.4.x-scala2.13", "17.3.x-scala2.13"]
      defaultValue = "15.4.x-scala2.12"
    }
    node_type_id = {
      type         = "allowlist"
      values       = ["i7i.2xlarge", "m7i.2xlarge", "c7i.4xlarge"]
      defaultValue = "m7i.2xlarge"
    }
    num_workers = {
      type         = "range"
      defaultValue = 1
      maxValue     = 2
      isOptional   = true
    }
    "autoscale.max_workers" = {
      type         = "range"
      defaultValue = 2
      maxValue     = 4
      isOptional   = true
    }
    "autoscale.min_workers" = {
      type         = "range"
      defaultValue = 1
      maxValue     = 2
      isOptional   = true
    }
    driver_node_type_id = {
      type         = "allowlist"
      values       = ["r7i.2xlarge", "m7i.2xlarge", "c7i.4xlarge"]
      defaultValue = "m7i.2xlarge"
      isOptional   = true
    }
    runtime_engine = {
      type   = "fixed"
      value  = "STANDARD"
      hidden = true
    }
    data_security_mode = {
      type  = "fixed"
      value = "SINGLE_USER"
    }
    "custom_tags.TYPE_OF_TASK" = {
      type  = "fixed"
      value = "job_large"
    }
    "custom_tags.COMPUTE_USERS" = {
      type  = "fixed"
      value = "STANDARD"
    }
  })
}

#personal compute 
resource "databricks_cluster_policy" "personal_compute" {
  name             = "Personal Compute"
  description      = "Create your own personal compute to run your notebooks.\nNode_type selection\nm7i - default all purpose compute\n- good for Small to mid-size databases.\nc7i - when more compute is needed and less on how much data to hold\n- Batch processing or Scientific modeling "
  policy_family_id = "personal-vm"
  policy_family_definition_overrides = jsonencode({
    node_type_id = {
      type         = "allowlist"
      values       = ["m7i.large", "c7i.xlarge"]
      defaultValue = "m7i.large"
    }
    spark_version = {
      type         = "allowlist"
      values       = ["15.4.x-scala2.12", "16.4.x-scala2.12", "17.3.x-scala2.13"]
      defaultValue = "15.4.x-scala2.12"
    }
    autotermination_minutes = {
      type  = "fixed"
      value = 30
    }
    "custom_tags.type_of_policy" = {
      type  = "fixed"
      value = "personal_compute"
    }
  })
}   