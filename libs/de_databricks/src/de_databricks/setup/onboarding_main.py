import datetime
import os
import sys

from de_toolbox.catalog import get_catalog

from de_databricks.iam.db_group import *


def create_users_and_group(meta):
    session = convert_session_account(create_databricks_session())
    email_list = meta["email_list"]
    group_name = f"{session.dev.lower()}_{meta['Catalog-name'].lower()}_owners"
    ### Create User if in DEV environment
    if session.env.lower() == "dev":
        for each in email_list:
            r = create_new_user(session, each)
    ### Create Account Level Group
    r = create_new_group(session, group_name, email_list)
    ### Assign Account Group to workspace
    r = create_update_permissions_assignment(session, group_name)

    ### Assigning entitement to group within workspace level
    session = create_databricks_session()
    r = update_group_details_entitlements(session, group_name, "platform_access")


def create_catalog_and_schemas(meta):
    # Rename json key for catalog
    meta["project"] = meta.pop("Catalog-name")

    # Get variables
    project = meta["project"]
    env = dbutils.widgets.get("ENV")
    vol_schema = dbutils.widgets.get("VOLUME_SCHEMA")
    volumes = dbutils.widgets.get("VOLUME_NAME")

    # Format catalog name
    project = project.replace(" ", "_").lower()
    catalog = get_catalog(project, env)

    # Create catalog and schemas
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
    spark.sql(f"USE CATALOG {catalog}")
    spark.sql("CREATE SCHEMA IF NOT EXISTS bronze")
    spark.sql("CREATE SCHEMA IF NOT EXISTS silver")
    spark.sql("CREATE SCHEMA IF NOT EXISTS gold")
    spark.sql("CREATE SCHEMA IF NOT EXISTS mart")

    # Grant Catalog
    grant_permission(spark, meta, env)

    # Create volumes for DART use cases
    c_owner_df = spark.sql(f"DESCRIBE CATALOG EXTENDED {catalog}").toPandas()
    c_owner = c_owner_df["info_value"][2]

    if not c_owner.endswith(".gov.sg"):
        for vol in str(volumes).split(","):
            v = vol.strip()
            spark.sql(
                f"GRANT READ VOLUME, WRITE VOLUME, CREATE VOLUME ON CATALOG {catalog} TO {env}_{project}_owners"
            )
            spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{vol_schema}.{v}")


def main():
    metadata = {
        "processing_time": datetime.datetime(2023, 10, 6, 6, 45, 16, 984000),
        "form_id": "6513c2938387e00012351d4d",
        "submission_id": "651b8424f14b170012a685ed",
        "Business_Value": "Service Delivery",
        "Catalog-name": "DEMOTESTER",
        "Dataset_Classification": "Restricted",
        "Dataset_Sensitivity": "Non-Sensitive",
        "Division": "CCYC",
        "Primary_Data_Source": "Compressed Parquet Files, SFTP into S3",
        "Remarks": "no",
        "Requestor_Name": "Jeffrey Siew",
        "Requestor's_Email_Address": "jeffrey_siew@tech.gov.sg",
        "Size_of_data": "1TB",
        "Use_Case": "Test use case for databricks",
        "Users": [
            {
                "user_name": "Jeffrey Siew",
                "user_email": "jeffrey_siew@tech.gov.sg",
                "user_role": "Data Owners - All privileges, including the ability to grant privileges to others.",
            },
            {
                "user_name": "Jeffrey Siew",
                "user_email": "jeffrey_siew@tech.gov.sg",
                "user_role": "Data Analysts - Perform Data Analysis",
            },
            {
                "user_name": "Jeffrey Siew",
                "user_email": "jeffrey_siew@tech.gov.sg",
                "user_role": "Data Engineers - Build Data Pipelines",
            },
        ],
    }

    create_catalog_and_schemas(metadata)
