# Databricks notebook source
# MAGIC %md
# MAGIC # Unity Catalog Migration Script Documentation
# MAGIC
# MAGIC ## Overview
# MAGIC
# MAGIC This script provides a comprehensive solution for migrating Unity Catalog objects from external catalogs to managed catalogs within Databricks. It replicates all catalog objects including schemas, tables, views, volumes, and their associated permissions whilst preserving metadata such as table and view comments.
# MAGIC
# MAGIC ## Key Features
# MAGIC
# MAGIC - **Complete Catalog Replication**: Migrates all schemas, tables, views, and volumes
# MAGIC - **Permission Preservation**: Maintains all non-inherited permissions at catalog, schema, table, view, and volume levels
# MAGIC - **Metadata Retention**: Preserves table and view comments/descriptions
# MAGIC - **Volume File Migration**: Copies all files within volumes to the new catalog
# MAGIC - **Automated Naming**: Creates target catalog with `_v2` suffix
# MAGIC - **Error Handling**: Robust error handling with detailed logging
# MAGIC
# MAGIC ## Prerequisites
# MAGIC
# MAGIC ### Service Principal Requirements
# MAGIC
# MAGIC This script **must be executed using a service principal** with the following permissions:
# MAGIC
# MAGIC **Source Catalog Permissions:**
# MAGIC - `USE CATALOG` on the source catalog
# MAGIC - `USE SCHEMA` on all schemas
# MAGIC - `SELECT` on all tables and views
# MAGIC - `READ FILES` on all volumes
# MAGIC - Permission to read Unity Catalog permissions via API
# MAGIC
# MAGIC **Target Environment Permissions:**
# MAGIC - `CREATE CATALOG` privilege in the metastore
# MAGIC - `USE CATALOG` on the target catalog (auto-granted as creator)
# MAGIC - Permission to assign catalogs to workspaces
# MAGIC - Permission to set Unity Catalog permissions via API
# MAGIC
# MAGIC **Storage Requirements:**
# MAGIC - Access to the specified managed storage location
# MAGIC - Appropriate cloud storage permissions (S3, ADLS, GCS)
# MAGIC
# MAGIC ### Technical Requirements
# MAGIC
# MAGIC - Databricks Runtime 13.0 or higher
# MAGIC - Unity Catalog enabled workspace
# MAGIC - Valid storage location for managed catalog
# MAGIC - Network connectivity to Databricks APIs
# MAGIC
# MAGIC ## Setup Instructions
# MAGIC
# MAGIC ### Step 1: Create Service Principal
# MAGIC
# MAGIC 1. Navigate to your Databricks workspace admin console
# MAGIC 2. Go to **Identity and Access** > **Service Principals**
# MAGIC 3. Click **Add Service Principal**
# MAGIC 4. Provide a name (e.g., `catalog-migration-sp`)
# MAGIC 5. Note down the **Application ID** and create a **Client Secret**
# MAGIC
# MAGIC ### Step 2: Grant Required Permissions
# MAGIC
# MAGIC Grant the service principal the necessary permissions on:
# MAGIC - Source catalog and all its objects
# MAGIC - Metastore (for catalog creation)
# MAGIC - Target storage location
# MAGIC
# MAGIC ### Step 3: Create Databricks Workflow
# MAGIC
# MAGIC **This script can only be executed via Databricks Workflows when using a service principal.**
# MAGIC
# MAGIC 1. Navigate to **Workflows** in your Databricks workspace
# MAGIC 2. Click **Create Job**
# MAGIC 3. Configure the job:
# MAGIC    - **Task Name**: `Catalog Migration`
# MAGIC    - **Type**: `Notebook`
# MAGIC    - **Source**: Upload or reference your migration notebook
# MAGIC    - **Cluster**: Create or select an appropriate cluster
# MAGIC    - **Advanced Options** > **Identity**: Select your service principal

# COMMAND ----------

from de_databricks.common.session import (
    create_databricks_session,
    create_databricks_workspace_session,
)
from de_databricks.migrate.db_catalog_migrate import create_and_replicate_catalog

# COMMAND ----------

# Usage example:
PROJECT = dbutils.widgets.get("PROJECT").lower()
ENV = dbutils.widgets.get("ENV").lower()
S3_BASE_PATH = f"s3://sst-s3-gvt-databricks-{ENV}-data"
# Get Workspace session
session = create_databricks_session()
new_catalog = create_and_replicate_catalog(
    spark, session, "migrate_dev", f"{S3_BASE_PATH}/{PROJECT}"
)

# COMMAND ----------
