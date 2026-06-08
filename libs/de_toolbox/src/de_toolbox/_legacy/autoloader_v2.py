import re

from databricks.sdk.runtime import *
from delta.tables import *
from pyspark.sql import functions as F


def create_bronze(spark, env, domain, subdomain, table, full_reload, *args):
    base_path = f"s3://sst-s3-gvt-databricks-{env}-autoloader"
    autoloader_path = f"{base_path}/{domain}/{subdomain}/{table}"

    # deletes any old checkpoint folders
    # rename the current checkpoint folders to "_old" to reset the checkpoint
    # drops the existing bronze and silver tables
    if full_reload:
        print("Full reload triggered...")
        try:
            dbutils.fs.rm(f"{autoloader_path}_old", recurse=True)
            dbutils.fs.mv(f"{autoloader_path}", f"{autoloader_path}_old", recurse=True)
            print("Full Reload: Checkpoint folders updated...")
        except Exception as e:
            if "java.io.FileNotFoundException" in str(e):
                print("Checkpoint folders not found, no need to reset checkpoint.")
            else:
                # Re-raise other exceptions if they are not related to file not found
                raise
        spark.sql(f"DROP TABLE IF EXISTS {domain}_{env}.{subdomain}.bronze_{table}")
        spark.sql(f"DROP TABLE IF EXISTS {domain}_{env}.{subdomain}.silver_{table}")
        print("Full Reload: Bronze and silver tables dropped (if exists)...")

    print(f"Loading files from '/Volumes/{domain}_{env}/{subdomain}/raw_data/{table}'")
    # load JSON files from raw data volume
    json_df = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("pathGlobfilter", "*.json")
        .option("multiLine", "true")
        .option("cloudFiles.schemaLocation", f"{autoloader_path}")
        .load(f"/Volumes/{domain}_{env}/{subdomain}/raw_data/{table}")
    )

    # load CSV files from raw data volume
    csv_df = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("pathGlobfilter", "*.csv")
        .option("quote", '"')
        .option("escape", '"')
        .option("multiLine", "true")
        .option("header", True)
        .option("cloudFiles.schemaLocation", f"{autoloader_path}")
        .load(f"/Volumes/{domain}_{env}/{subdomain}/raw_data/{table}")
    )

    # union all the input files
    # input_df = json_df.unionByName(csv_df)
    input_df = json_df

    # drop any pre-defined columns (if any)
    if args[0]["drop_columns"]:
        input_df = input_df.drop(*args[0]["drop_columns"])

    # sanitise columns for each record to prevent any invalid column chars
    # r'[^A-Za-z0-9_]+' is a regex pattern that matches any character NOT in the set
    clean_col_df = [re.sub(r"[^A-Za-z0-9_]+", "_", col_name) for col_name in input_df.columns]
    input_df = input_df.toDF(*clean_col_df)

    # generate SHA256 hash column for each record
    input_string_df = input_df.select(
        [
            F.to_json(F.col(c)).alias(c)
            if dict(input_df.dtypes)[c]
            not in ["string", "int", "double", "float", "date", "timestamp", "boolean"]
            else F.col(c)
            for c in input_df.columns
        ]
    )
    input_df = input_df.withColumn(
        "Hash_Key", F.sha2(F.concat_ws("|", *input_string_df.columns), 256)
    )

    # generate _LOAD_DTS column
    input_df = input_df.withColumn("_LOAD_DTS", F.current_timestamp())

    # generate _INGEST_DATE column
    input_df = input_df.withColumn("Source_File", F.col("_metadata.file_name"))
    input_df = input_df.withColumn(
        "_INGEST_DATE", F.substring_index(input_df["Source_File"], "_", -1)
    )
    input_df = input_df.withColumn(
        "_INGEST_DATE", F.regexp_replace(F.col("_INGEST_DATE"), r"\.[^.]+$", "")
    )
    input_df = input_df.withColumn("_INGEST_DATE", F.to_date(F.col("_INGEST_DATE"), "yyyyMMdd"))

    # write the stream into the bronze table
    table_path = f"{domain}_{env}.{subdomain}.bronze_{table}"
    print(f"Writing stream to bronze table {table_path}")
    input_df.writeStream.option("mergeSchema", "true").option(
        "checkpointLocation", f"{autoloader_path}"
    ).trigger(availableNow=True).toTable(f"{table_path}")


def create_silver(spark, env, domain, subdomain, table, schema_config):
    bronze_path = f"{domain}_{env}.{subdomain}.bronze_{table}"
    silver_path = f"{domain}_{env}.{subdomain}.silver_{table}"

    if spark.catalog.tableExists(silver_path):
        print(f"Table {silver_path} already exists, appending updates...")

        # Get the most recent LOAD_DTS timestamp in silver
        max_load_dts = spark.sql(
            f"SELECT MAX(_LOAD_DTS) AS max_load_dts FROM {silver_path}"
        ).collect()[0][0]
        bronze_delta_df = spark.sql(
            f"SELECT * FROM {bronze_path} WHERE _LOAD_DTS > '{max_load_dts}'"
        )

        # Cast the required columns in bronze delta records
        bronze_delta_df = cast_columns(bronze_delta_df, schema_config)
        bronze_delta_df = bronze_delta_df.drop("Source_File", "_rescued_data")

        # Append the bronze delta records into silver
        bronze_delta_df.write.format("delta").option("mergeSchema", "true").mode(
            "append"
        ).saveAsTable(f"{silver_path}")
    else:
        # prepare first load silver table
        print(f"Table {silver_path} does not exist, creating it...")

        silver_df = spark.sql(f"SELECT * FROM {bronze_path}")

        # Cast the required columns for the silver table
        silver_df = cast_columns(silver_df, schema_config)
        silver_df = silver_df.drop("Source_File", "_rescued_data")
        silver_df.createOrReplaceTempView("silver_temp")

        spark.sql(f"CREATE TABLE {silver_path} AS SELECT * FROM silver_temp")


def cast_columns(input_df, schema_config):
    for column_name, target_type in schema_config.items():
        # Check if the column exists in the DataFrame
        if column_name in input_df.columns:
            if target_type == "JSON":
                # Special handling for VARIANT types
                input_df = input_df.withColumn(column_name, F.parse_json(F.col(column_name)))
            else:
                input_df = input_df.withColumn(column_name, F.col(column_name).cast(target_type))
        else:
            print(f"Warning: Column '{column_name}' not found in DataFrame.")

    return input_df
