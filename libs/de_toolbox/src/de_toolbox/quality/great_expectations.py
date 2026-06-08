import ast
import os
import sys

import great_expectations as gx
import pandas as pd
from great_expectations.checkpoint import Checkpoint
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, max, to_date

from de_toolbox.catalog import get_catalog, get_repo_path

path = "/Workspace/Repos/shared/de_databricks"
if path not in sys.path:
    sys.path.append(os.path.abspath(path))
from account.iam import *
from common.session import *


# Set up 1 -------------------------------------------------------------------------------------------------------------------------
def dq_setup_1():

    global context
    context = gx.get_context(project_root_dir=context_root_dir)
    data_source = context.sources.add_spark(f"{domain}_data_source")
    data_asset = data_source.add_dataframe_asset(name=f"{table}_data_asset")
    context.add_or_update_expectation_suite(expectation_suite_name=f"{domain}_expectation_suite")
    return context


# Set up 2  -------------------------------------------------------------------------------------------------------------------
def dq_setup_2(spark):

    global context, batch_request
    df = spark.read.table(f"{catalog}.{schema}.{table}").select(*cde)

    if "_LOAD_DTS" in cde:
        date_count = df.groupBy("_LOAD_DTS").count().count()
        if date_count > 1:
            most_recent_date = df.select(max("_LOAD_DTS")).collect()[0][0]
            df = df.filter(col("_LOAD_DTS") == most_recent_date)
    elif "_INGEST_DTS" in cde:
        date_count = df.groupBy("_INGEST_DTS").count().count()
        if date_count > 1:
            most_recent_date = df.select(max("_INGEST_DTS")).collect()[0][0]
            df = df.filter(col("_INGEST_DTS") == most_recent_date)
    else:
        df

    context = gx.get_context(project_root_dir=context_root_dir)
    data_source = context.get_datasource(f"{domain}_data_source")

    try:
        data_asset = data_source.add_dataframe_asset(name=f"{table}_data_asset")
    except ValueError:
        data_asset = context.get_datasource(f"{domain}_data_source").get_asset(
            f"{table}_data_asset"
        )

    batch_request = data_asset.build_batch_request(dataframe=df)

    return context, batch_request


# Add Expectations -------------------------------------------------------------------------------------------------------------------------------------------
def add_expectations():

    validator = context.get_validator(
        batch_request=batch_request, expectation_suite_name=f"{domain}_expectation_suite"
    )

    for col in completeness:
        validator.expect_column_values_to_not_be_null(
            column=col, meta={"Dimension": "Completeness"}
        )

    for item in conformity:
        eval(f"validator.{item['function']}({item['expression']})")

    for item in validity:
        eval(f"validator.{item['function']}({item['expression']})")

    for col in uniqueness:
        validator.expect_column_values_to_be_unique(column=col, meta={"Dimension": "Uniqueness"})

    validator.save_expectation_suite(discard_failed_expectations=False)


# Create and Run Checkpoint ---------------------------------------------------------------------------------------------------------------------------------
def run_checkpoint():

    global checkpoint_result

    checkpoint = Checkpoint(
        name=f"{domain}_checkpoint",
        run_name_template="%Y%m%d-%H%M%S-my-run-name-temple",
        data_context=context,
        batch_request=batch_request,
        expectation_suite_name=f"{domain}_expectation_suite",
        action_list=[
            {
                "name": "store_validation_result",
                "action": {"class_name": "StoreValidationResultAction"},
            },
            {"name": "update_data_docs", "action": {"class_name": "UpdateDataDocsAction"}},
        ],
        runtime_configuration={
            "result_format": {
                "result_format": "BASIC"
                # "unexpected_index_column_names": [pk],
                # "unexpected_index_list": True,
            },
            "catch_exceptions": True,
        },
    )

    # Update and run Checkpoint
    context.add_or_update_checkpoint(checkpoint=checkpoint)
    checkpoint_result = checkpoint.run()

    return checkpoint_result


# Create Lvl1 Table ------------------------------------------------------------------------------------------------------------------------------------
def lvl1_table(spark):

    # Datetime
    last_refreshed_date = pd.to_datetime("today").normalize()

    # Initialize lists to store data
    column_names = []
    dimensions = []
    success_rates = []

    # Extract data from JSON
    for key, value in checkpoint_result["run_results"].items():
        validation_result = value["validation_result"]

        for result in validation_result["results"]:
            try:
                column_name = result["expectation_config"]["kwargs"]["column"]
                dimensions_list = result["expectation_config"]["meta"]["Dimension"]

                # Ensure dimensions_list is a list
                if not isinstance(dimensions_list, list):
                    dimensions_list = [dimensions_list]

                element_count = result["result"]["element_count"]
                unexpected_count = result["result"]["unexpected_count"]

                # Calculate Passed count
                if element_count != 0:
                    passed_count = element_count - unexpected_count
                else:
                    passed_count = 0

                # Calculate success rate
                if element_count != 0:
                    success_rate = round((passed_count / element_count) * 100, 2)
                else:
                    success_rate = 0

                # Append data to lists, one row for each dimension
                for dimension in dimensions_list:
                    column_names.append(column_name)
                    dimensions.append(dimension)
                    success_rates.append(success_rate)

            except KeyError:
                continue

    # Create DataFrame
    df = pd.DataFrame(
        {
            "Domain": domain,
            "Sub-Domain": subdomain,
            "Table": table,
            "Column_Name": column_names,
            "Dimension": dimensions,
            "Success_Rate": success_rates,
            "Last_Refreshed_Date": last_refreshed_date,
        }
    )

    df_domain = (
        df.groupby(
            ["Domain", "Sub-Domain", "Table", "Dimension", "Last_Refreshed_Date"], as_index=False
        )
        .agg({"Success_Rate": "mean"})
        .round({"Success_Rate": 2})
    )

    # Convert into Spark DataFrame and write to Table
    spark_df = spark.createDataFrame(df)
    spark_df = spark_df.withColumn("Last_Refreshed_Date", to_date(col("Last_Refreshed_Date")))
    spark_df.write.option("mergeSchema", "true").mode("append").saveAsTable(
        f"{output_catalog}.{output_schema}.{output_table1}"
    )

    spark_df = spark.createDataFrame(df_domain)
    spark_df = spark_df.withColumn("Last_Refreshed_Date", to_date(col("Last_Refreshed_Date")))
    spark_df.write.option("mergeSchema", "true").mode("append").saveAsTable(
        f"{output_catalog}.{output_schema}.{output_table2}"
    )


# Final Function -----------------------------------------------------------------------------------------------------------------------
def main(metadata, project, env, first_table):
    spark = SparkSession.builder.appName("DQ Checks").getOrCreate()

    global \
        context_root_dir, \
        catalog, \
        schema, \
        table, \
        pk, \
        domain, \
        subdomain, \
        output_catalog, \
        output_schema, \
        output_table1, \
        output_table2, \
        completeness, \
        conformity, \
        uniqueness, \
        validity, \
        cde

    # Create Catalog and schema if not exists
    output_catalog = f"databricks_dq_{env}"

    spark.sql(f"CREATE CATALOG IF NOT EXISTS {output_catalog}")
    spark.sql(f"USE CATALOG {output_catalog}")

    session = create_databricks_session()
    org_id = spark.conf.get("spark.databricks.clusterUsageTags.clusterOwnerOrgId")
    is_prd = org_id.endswith("5212")

    if is_prd:
        principal = create_or_get_service_principal(session, "prd_admin_principal")
        prd_p_id = principal["applicationId"]
        spark.sql(
            f"GRANT USE_CATALOG, USE_SCHEMA, CREATE_SCHEMA, CREATE_TABLE, CREATE_VOLUME, READ_VOLUME, WRITE_VOLUME, MODIFY, SELECT ON CATALOG {output_catalog} TO `{prd_p_id}`"
        )
    else:
        principal = create_or_get_service_principal(session, "uat_admin_principal")
        uat_p_id = principal["applicationId"]
        spark.sql(
            f"GRANT USE_CATALOG, USE_SCHEMA, CREATE_SCHEMA, CREATE_TABLE, CREATE_VOLUME, READ_VOLUME, WRITE_VOLUME, MODIFY, SELECT ON CATALOG {output_catalog} TO `{uat_p_id}`"
        )

    spark.sql(f"CREATE SCHEMA if not exists {output_catalog}.{project}")

    if project == "toolbox":
        spark.sql(f"ALTER CATALOG {output_catalog} OWNER TO `{env}_dart_owners`")
        spark.sql(f"ALTER SCHEMA {project} OWNER TO `{env}_dart_owners`")
        read_catalog = f"test_{env}"
    else:
        spark.sql(f"ALTER CATALOG {output_catalog} OWNER TO `{env}_dart_owners`")
        spark.sql(f"ALTER SCHEMA {project} OWNER TO `{env}_dart_owners`")
        read_catalog = get_catalog(project, env)

    if is_prd:
        spark.sql(
            f"GRANT USE_CATALOG, USE_SCHEMA, READ_VOLUME ON CATALOG {output_catalog} TO `{env}_dart_dm`"
        )
        spark.sql(f"GRANT SELECT ON SCHEMA {output_catalog}.{project} TO `{env}_dart_dm`")
    else:
        spark.sql(
            f"GRANT USE_CATALOG, USE_SCHEMA, READ_VOLUME ON CATALOG {output_catalog} TO `{env}_dart_dm`"
        )
        spark.sql(f"GRANT SELECT ON SCHEMA {output_catalog}.{project} TO `{env}_dart_dm`")

    # Metadata Extraction ----------------------

    base_path = get_repo_path(project, debug=None, folder="data_quality")
    metadata_path = f"{base_path}/{metadata}.json"

    env_dic = {"ENV": f"{env}", "PROJECT": f"{project}"}
    metadata = open(metadata_path).read()
    for k, v in env_dic.items():
        metadata = metadata.replace("{{ " + k + " }}", v)
    metadata = ast.literal_eval(metadata)

    catalog = get_catalog(project, env)
    schema = metadata["schema"]
    table = metadata["table"]
    pk = metadata["primary_key"]

    domain = metadata["domain"]
    subdomain = metadata["subdomain"]

    output_schema = project
    output_table1 = f"{table}_dq_agg"
    output_table2 = f"{domain}_dq_agg"

    cde = metadata["cde"]
    completeness = metadata["completeness"]
    conformity = metadata["conformity"]
    validity = metadata["validity"]
    uniqueness = metadata["uniqueness"]

    spark.sql(f"CREATE VOLUME IF NOT EXISTS {output_catalog}.{project}.great_expectations")

    context_root_dir = f"/Volumes/{output_catalog}/{project}/great_expectations"

    # Calling other functions ---------------------------------------------------------------
    if first_table.lower() == "yes":
        dq_setup_1()
        dq_setup_2(spark)
        add_expectations()
        run_checkpoint()
        lvl1_table(spark)
    elif first_table.lower() == "no":
        dq_setup_2(spark)
        add_expectations()
        run_checkpoint()
        lvl1_table(spark)
    else:
        raise ValueError("first_table must be either 'yes' or 'no'")
