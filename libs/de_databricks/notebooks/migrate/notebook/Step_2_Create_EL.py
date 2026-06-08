# Databricks notebook source
# MAGIC %md
# MAGIC # Storage Configuration Setup: Single External Location & Permissions
# MAGIC
# MAGIC ## Overview
# MAGIC
# MAGIC This notebook sets up a single storage credential, one external location at the S3 bucket root, and assigns CREATE MANAGED STORAGE permissions to all catalog admin service principals for migration projects.
# MAGIC
# MAGIC ## Prerequisites
# MAGIC
# MAGIC ⚠️ **IMPORTANT**: This script must be executed by an **Account Admin** after service principals have been created.
# MAGIC
# MAGIC ### Required Components
# MAGIC - **Account Admin** privileges in Databricks
# MAGIC - **Catalog Admin Service Principals** already created (format: `sp_{env}_cdo_catalog_admin_{project}`)
# MAGIC - **IAM Role ARN** for S3 bucket access (provided by AWS team)
# MAGIC - **S3 Bucket root path** for all catalogs
# MAGIC - Unity Catalog enabled workspace
# MAGIC - AWS IAM role configured with appropriate S3 permissions
# MAGIC
# MAGIC ### Dependencies
# MAGIC - Databricks session with appropriate authentication
# MAGIC - Unity Catalog enabled workspace
# MAGIC - Service principals already created with naming convention: `sp_{env}_cdo_catalog_admin_{project}`
# MAGIC
# MAGIC ## When to Run This Script
# MAGIC
# MAGIC ### Timing
# MAGIC - **After service principals have been created**
# MAGIC - After Unity Catalog setup is complete
# MAGIC - After AWS IAM role is provisioned and configured
# MAGIC - Before any data migration activities begin
# MAGIC
# MAGIC ### Environment Sequence
# MAGIC 1. Run for `dev` environment first
# MAGIC 2. Run for `uat` environment after dev validation
# MAGIC 3. Run for `prd` environment last

# COMMAND ----------

from de_databricks.common.session import (
    create_databricks_session,
    create_databricks_workspace_session,
)
from de_databricks.unitycatalog.db_unity_catalog import assign_catalog_to_workspace

# COMMAND ----------


## Storage Configuration Script
def get_catalog_admin_service_principals(session, env):
    """Get all catalog admin service principals for the specified environment"""
    try:
        # Get all service principals
        response = session.get("/api/2.0/preview/scim/v2/ServicePrincipals")

        if response.status_code != 200:
            print(
                f"❌ Failed to fetch service principals: {response.status_code} - {response.text}"
            )
            return []

        service_principals = response.json().get("Resources", [])

        # Filter for catalog admin service principals matching the environment
        prefix = f"sp_{env}_cdo_catalog_admin"
        catalog_admin_sps = []

        for sp in service_principals:
            sp_name = sp.get("displayName", "")
            if sp_name.startswith(prefix):
                # Extract project name from SP name
                # Format: sp_{env}_cdo_catalog_admin_{project}
                project = sp_name.replace(f"{prefix}_", "")
                catalog_admin_sps.append(
                    {
                        "name": sp_name,
                        "application_id": sp.get("applicationId"),
                        "project": project,
                        "catalog": f"{project}_{env}",
                    }
                )

        return catalog_admin_sps

    except Exception as e:
        print(f"❌ Error fetching service principals: {e}")
        return []


def create_storage_credential(session, cred_name, iam_role_arn, comment=""):
    """Create a storage credential using IAM role"""
    try:
        payload = {
            "name": cred_name,
            "aws_iam_role": {"role_arn": iam_role_arn},
            "comment": comment,
        }

        response = session.post("/api/2.1/unity-catalog/storage-credentials", json=payload)

        if response.status_code == 200:
            print(f"✅ Created storage credential: {cred_name}")
            return response.json()
        elif response.status_code == 409:
            print(f"⚠️  Storage credential already exists: {cred_name}")
            # Get existing credential
            get_response = session.get(f"/api/2.1/unity-catalog/storage-credentials/{cred_name}")
            return get_response.json()
        else:
            print(
                f"❌ Failed to create storage credential {cred_name}: {response.status_code} - {response.text}"
            )
            return None

    except Exception as e:
        print(f"❌ Error creating storage credential {cred_name}: {e}")
        return None


def create_external_location(session, location_name, s3_path, storage_cred_name, comment=""):
    """Create an external location using storage credential"""
    try:
        payload = {
            "name": location_name,
            "url": s3_path,
            "credential_name": storage_cred_name,
            "comment": comment,
        }

        response = session.post("/api/2.1/unity-catalog/external-locations", json=payload)

        if response.status_code == 200:
            print(f"✅ Created external location: {location_name}")
            return response.json()
        elif response.status_code == 409:
            print(f"⚠️  External location already exists: {location_name}")
            # Get existing location
            get_response = session.get(f"/api/2.1/unity-catalog/external-locations/{location_name}")
            return get_response.json()
        else:
            print(
                f"❌ Failed to create external location {location_name}: {response.status_code} - {response.text}"
            )
            return None

    except Exception as e:
        print(f"❌ Error creating external location {location_name}: {e}")
        return None


def grant_create_managed_storage_permission(sp_application_id, external_location_name):
    """Grant CREATE MANAGED STORAGE permission to service principal"""
    try:
        grant_sql = f"GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION `{external_location_name}` TO `{sp_application_id}`"
        print(f"Executing: {grant_sql}")
        spark.sql(grant_sql)
        print(
            f"✅ Granted CREATE MANAGED STORAGE permission to {sp_application_id} on {external_location_name}"
        )
        return True
    except Exception as e:
        print(f"❌ Error granting CREATE MANAGED STORAGE permission: {e}")
        return False


def setup_migration_storage(session, env, iam_role_arn, s3_bucket_root):
    """
    Setup single storage credential, external location, and permissions for migration

    Args:
        session: Databricks API session
        env: Environment (dev, uat, prd)
        iam_role_arn: AWS IAM role ARN for S3 bucket access
        s3_bucket_root: Root S3 path (e.g., 's3://migration-bucket-dev/')
    """

    print(f"🗄️  STARTING STORAGE SETUP FOR ENVIRONMENT: {env.upper()} 🗄️")
    print("=" * 80)

    # Define resource names
    storage_cred_name = f"storage_cred_migration_{env}"
    external_location_name = f"ext_loc_migration_{env}"

    # 1. Get catalog admin service principals
    print("--- Retrieving Catalog Admin Service Principals ---")
    catalog_admin_sps = get_catalog_admin_service_principals(session, env)

    if not catalog_admin_sps:
        print(f"❌ No catalog admin service principals found for environment {env}")
        print(f"   Expected format: sp_{env}_cdo_catalog_admin_{{project}}")
        return None

    print(f"Found {len(catalog_admin_sps)} catalog admin service principals:")
    for sp in catalog_admin_sps:
        print(f"  - {sp['name']} (Project: {sp['project']}, App ID: {sp['application_id']})")

    # 2. Create storage credential
    print(f"\n--- Creating Storage Credential: {storage_cred_name} ---")
    storage_cred = create_storage_credential(
        session,
        storage_cred_name,
        iam_role_arn,
        f"Storage credential for migration {env} environment",
    )

    if not storage_cred:
        print(f"❌ Failed to create storage credential for {env} environment")
        return None

    # 3. Create external location
    print(f"--- Creating External Location: {external_location_name} ---")
    external_location = create_external_location(
        session,
        external_location_name,
        s3_bucket_root,
        storage_cred_name,
        f"External location for migration {env} environment - bucket root access",
    )

    if not external_location:
        print(f"❌ Failed to create external location for {env} environment")
        return None

    # 4. Grant CREATE MANAGED STORAGE permission to all catalog admin service principals
    print("\n--- Granting CREATE MANAGED STORAGE Permissions ---")
    permission_results = {}
    successful_grants = 0

    for sp in catalog_admin_sps:
        print(f"Granting permission to {sp['name']} ({sp['application_id']})...")
        permission_granted = grant_create_managed_storage_permission(
            sp["application_id"], external_location_name
        )
        permission_results[sp["name"]] = permission_granted
        if permission_granted:
            successful_grants += 1

    # 5. Summary
    print(f"\n🎉 STORAGE SETUP SUMMARY FOR {env.upper()}")
    print("=" * 80)

    print("📋 SERVICE PRINCIPALS FOUND:")
    for sp in catalog_admin_sps:
        print(f"  - {sp['name']} → Catalog: {sp['catalog']}")

    print("\n🗄️  STORAGE RESOURCES CREATED:")
    print(f"  - Storage Credential: {storage_cred_name}")
    print(f"  - External Location: {external_location_name}")
    print(f"  - S3 Bucket Root: {s3_bucket_root}")
    print(f"  - IAM Role: {iam_role_arn}")

    print("\n🔐 PERMISSION GRANTS:")
    print(f"  Total service principals: {len(catalog_admin_sps)}")
    print(f"  Successful grants: {successful_grants}")
    print(f"  Failed grants: {len(catalog_admin_sps) - successful_grants}")

    for sp_name, granted in permission_results.items():
        status = "✅ Granted" if granted else "❌ Failed"
        print(f"    {sp_name}: {status}")

    print("\n📝 NEXT STEPS:")
    print(
        f"  1. Verify external location access with: LIST '{s3_bucket_root}' USING EXTERNAL LOCATION `{external_location_name}`"
    )
    print("  2. Test managed table creation in each catalog")
    print("  3. Proceed with data migration activities")

    return {
        "storage_credential": storage_cred,
        "external_location": external_location,
        "service_principals": catalog_admin_sps,
        "permission_results": permission_results,
        "summary": {
            "total_service_principals": len(catalog_admin_sps),
            "successful_grants": successful_grants,
            "failed_grants": len(catalog_admin_sps) - successful_grants,
            "all_permissions_granted": successful_grants == len(catalog_admin_sps),
        },
    }


# COMMAND ----------

# Set environment
ENV = "dev"  # Change to "uat" or "prd" as needed

# Configure storage settings - single IAM role and S3 bucket root
IAM_ROLE_ARN = "arn:aws:iam::123456789012:role/migration-dev-s3-access-role"
S3_BUCKET_ROOT = "s3://migration-bucket-dev/"

# Ensure you have account admin session
session = create_databricks_session()

# Run storage configuration setup
results = setup_migration_storage(session, ENV, IAM_ROLE_ARN, S3_BUCKET_ROOT)
