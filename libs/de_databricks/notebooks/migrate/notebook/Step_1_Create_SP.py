# Databricks notebook source
# MAGIC %md
# MAGIC # Service Principal Creation for Migration Project
# MAGIC
# MAGIC ## Overview
# MAGIC
# MAGIC This notebook contains scripts to create and configure service principals required for the migration project. The service principals are created with appropriate Unity Catalog permissions to support the migration process across different environments.
# MAGIC
# MAGIC ## Prerequisites
# MAGIC
# MAGIC ⚠️ **IMPORTANT**: This script must be executed by an **Account Admin** before migration implementation begins.
# MAGIC
# MAGIC ### Required Permissions
# MAGIC - **Account Admin** privileges in Databricks
# MAGIC - Access to Unity Catalog metastore
# MAGIC - Ability to create service principals at account level
# MAGIC
# MAGIC ### Dependencies
# MAGIC - Databricks session with appropriate authentication
# MAGIC - `create_or_get_service_principal()` function (must be defined separately)
# MAGIC - Unity Catalog enabled workspace
# MAGIC
# MAGIC ## When to Run This Script
# MAGIC
# MAGIC ### Timing
# MAGIC - **Before migration implementation starts**
# MAGIC - After Unity Catalog setup is complete
# MAGIC - Before any data migration activities begin

# COMMAND ----------

from de_databricks.account.iam import (
    create_or_get_service_principal,
    create_or_update_service_principal_token,
)
from de_databricks.common.session import (
    create_databricks_session,
    create_databricks_workspace_session,
)
from de_databricks.unitycatalog.db_unity_catalog import get_catalogs_for_env

# COMMAND ----------


def assign_metastore_permissions(spark, sp_id, catalog_name):
    """Assign MANAGE permission to service principal for a specific catalog using SQL"""
    # Define grants outside try-except and loop
    grants = [
        f"GRANT USE CATALOG ON CATALOG `{catalog_name}` TO `{sp_id}`",
        f"GRANT USE SCHEMA ON CATALOG `{catalog_name}` TO `{sp_id}`",
        f"GRANT MANAGE ON CATALOG `{catalog_name}` TO `{sp_id}`",
    ]

    success_count = 0
    for grant_sql in grants:
        try:
            print(f"Executing: {grant_sql}")
            spark.sql(grant_sql)
            success_count += 1
        except Exception as e:
            print(f"❌ Error executing grant: {grant_sql}")
            # print(f"   Error details: {e}")

    if success_count == len(grants):
        print(f"✅ Assigned metastore admin permissions to {sp_id} for catalog {catalog_name}")
        return True
    else:
        print(
            f"⚠️  Partial success: {success_count}/{len(grants)} grants succeeded for {sp_id} on catalog {catalog_name}"
        )
        return False


def assign_catalog_admin_permissions(spark, sp_id, catalog_name):
    """Assign ALL PRIVILEGES permissions to catalog admin using SQL"""
    # Define grants outside try-except and loop
    grants = [f"GRANT ALL PRIVILEGES ON CATALOG `{catalog_name}` TO `{sp_id}`"]

    success_count = 0
    for grant_sql in grants:
        try:
            print(f"Executing: {grant_sql}")
            spark.sql(grant_sql)
            success_count += 1
        except Exception as e:
            print(f"❌ Error executing grant: {grant_sql}")
            # print(f"   Error details: {e}")

    if success_count == len(grants):
        print(f"✅ Assigned catalog admin permissions to {sp_id} for catalog {catalog_name}")
        return True
    else:
        print(
            f"⚠️  Partial success: {success_count}/{len(grants)} grants succeeded for {sp_id} on catalog {catalog_name}"
        )
        return False


def create_service_principals_for_env(spark, session, env, team="cdo"):
    """
    Create service principals for a specific environment

    Args:
        session: Databricks session
        env: Environment (dev, uat, prd)
        team: Team name (default: cdo)
    """

    print(f"Creating service principals for environment: {env}")

    # 1. Create account admin SP
    account_admin_name = f"sp_{env}_{team}_account_admin"
    print(f"--- Creating Account Admin SP: {account_admin_name} ---")
    account_admin_sp = create_or_get_service_principal(session, account_admin_name)

    # 2. Create metastore admin SP
    metastore_admin_name = f"sp_{env}_{team}_metastore_admin"
    print(f"--- Creating Metastore Admin SP: {metastore_admin_name} ---")
    metastore_admin_sp = create_or_get_service_principal(session, metastore_admin_name)

    # Get metastore admin application ID for permissions
    metastore_admin_id = metastore_admin_sp.get("applicationId")

    # 3. Get catalogs for this environment
    catalogs = get_catalogs_for_env(session, env)
    print(f"Found {len(catalogs)} catalogs for environment {env}:")
    for cat in catalogs:
        print(f"  - {cat['name']}")

    # 4. Assign metastore admin permissions to all catalogs
    if metastore_admin_id and catalogs:
        print("--- Assigning Metastore Admin permissions ---")
        for catalog in catalogs:
            catalog_name = catalog["name"]
            assign_metastore_permissions(spark, metastore_admin_id, catalog_name)

    # 5. Create catalog admin SPs for each catalog
    catalog_admins = {}
    for catalog in catalogs:
        catalog_name = catalog["name"]
        # Extract project name from catalog (assuming format: {PROJECT}_{ENV})
        project = catalog_name.replace(f"_{env}", "")

        catalog_admin_name = f"sp_{env}_{team}_catalog_admin_{project}"
        print(f"--- Creating Catalog Admin SP: {catalog_admin_name} ---")

        catalog_admin_sp = create_or_get_service_principal(session, catalog_admin_name)
        catalog_admin_id = catalog_admin_sp.get("applicationId")

        if catalog_admin_id:
            # Assign permissions to their specific catalog
            assign_catalog_admin_permissions(spark, catalog_admin_id, catalog_name)
            catalog_admins[project] = {
                "sp_name": catalog_admin_name,
                "sp_id": catalog_admin_id,
                "catalog": catalog_name,
            }

    # Summary
    print(f"=== SUMMARY for Environment: {env} ===")
    print(f"Account Admin SP: {account_admin_name}")
    print(f"Metastore Admin SP: {metastore_admin_name}")
    print(f"Catalog Admin SPs created: {len(catalog_admins)}")
    for project, details in catalog_admins.items():
        print(f"  - {details['sp_name']} (for catalog: {details['catalog']})")

    return {
        "account_admin": account_admin_sp,
        "metastore_admin": metastore_admin_sp,
        "catalog_admins": catalog_admins,
    }


# COMMAND ----------


# Usage example:
def main():
    # Set your environment here
    ENV = "dev"  # Change this to "uat" or "prd" as needed

    # Create session
    session = create_databricks_session()

    # Create all service principals for the environment
    result = create_service_principals_for_env(spark, session, ENV)

    print(f"✅ Service principal creation completed for environment: {ENV}")


# Run the script
if __name__ == "__main__":
    main()

# COMMAND ----------
