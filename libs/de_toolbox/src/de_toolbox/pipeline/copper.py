"""Copper layer — Auto Loader ingestion from raw files (JSON/CSV).

Reads from Databricks Volumes via structured streaming, applies minimal
column cleaning for column mapping compatibility, and writes to a Delta table.
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from de_toolbox.pipeline.column_cleaning import clean_columns_for_column_mapping


def create_copper_table(
    spark: SparkSession,
    dbutils,
    env: str,
    table_name: str,
    full_reload: bool,
    config_dict: dict,
) -> None:
    """Ingest raw files into a copper-layer Delta table via Auto Loader.

    Args:
        spark: Active SparkSession.
        dbutils: Databricks utilities (for fs operations).
        env: Environment (dev, stg, prd).
        table_name: Target table name (without prefix).
        full_reload: If True, drops existing table and resets checkpoints.
        config_dict: Configuration dict with keys:
            - domain: str
            - subdomain: str
            - copper: {file_format, drop_columns, ingest_timestamp_column,
                       ingest_date_format, column_naming_convention}
    """

    def _table_exists(spark, path):
        try:
            spark.sql(f"DESCRIBE {path}").collect()
            return True
        except Exception:
            return False

    def _has_column_mapping(spark, path):
        try:
            props = spark.sql(f"SHOW TBLPROPERTIES {path} ('delta.columnMapping.mode')").collect()
            return props and props[0][1] == "id"
        except Exception:
            return False

    domain = config_dict.get("domain", "default_domain")
    subdomain = config_dict.get("subdomain", "default")
    autoloader_config = config_dict.get("copper", {})

    ingest_timestamp_column = autoloader_config.get("ingest_timestamp_column")
    ingest_date_format = autoloader_config.get("ingest_date_format")
    drop_columns = autoloader_config.get("drop_columns", [])
    file_format = autoloader_config.get("file_format", "csv")

    base_path = f"s3://sst-s3-gvt-databricks-{env}-autoloader"
    autoloader_path = f"{base_path}/{domain}/{subdomain}/{table_name}"
    dbutils.fs.mkdirs(autoloader_path)
    table_path = f"{domain}_{env}.{subdomain}.copper_{table_name}"

    original_full_reload = full_reload
    if _table_exists(spark, table_path) and not _has_column_mapping(spark, table_path):
        full_reload = True

    if full_reload:
        print(
            f"Full reload triggered"
            f"{' (auto: column mapping)' if not original_full_reload else ''}..."
        )
        try:
            dbutils.fs.rm(f"{autoloader_path}_old", recurse=True)
            dbutils.fs.mv(autoloader_path, f"{autoloader_path}_old", recurse=True)
        except Exception as e:
            if "java.io.FileNotFoundException" not in str(e):
                raise
        spark.sql(f"DROP TABLE IF EXISTS {domain}_{env}.{subdomain}.copper_{table_name}")
        spark.sql(f"DROP TABLE IF EXISTS {domain}_{env}.{subdomain}.bronze_{table_name}")

    if not _table_exists(spark, table_path):
        spark.sql(f"""
        CREATE TABLE {table_path} (_temp STRING)
        USING DELTA TBLPROPERTIES ('delta.columnMapping.mode' = 'id')
        """)

    print(f"Loading from '/Volumes/{domain}_{env}/{subdomain}/raw_data/{table_name}'")

    load_path = f"/Volumes/{domain}_{env}/{subdomain}/raw_data/{table_name}"

    if file_format.lower() == "json":
        input_df = (
            spark.readStream.format("cloudFiles")
            .option("cloudFiles.inferColumnTypes", "true")
            .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
            .option("cloudFiles.inferSchema", "true")
            .option("cloudFiles.format", "json")
            .option("pathGlobfilter", "*.json")
            .option("multiLine", "true")
            .option("cloudFiles.schemaLocation", autoloader_path)
            .load(load_path)
        )
    elif file_format.lower() == "csv":
        input_df = (
            spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", "csv")
            .option("cloudFiles.inferColumnTypes", "true")
            .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
            .option("cloudFiles.inferSchema", "true")
            .option("pathGlobfilter", "*.csv")
            .option("quote", '"')
            .option("escape", '"')
            .option("multiLine", "true")
            .option("header", True)
            .option("cloudFiles.schemaLocation", autoloader_path)
            .load(load_path)
        )
    else:
        raise ValueError(f"Unsupported file_format: {file_format}")

    if drop_columns:
        input_df = input_df.drop(*drop_columns)

    original_columns = input_df.columns
    input_df, column_mapping = clean_columns_for_column_mapping(input_df)

    original_to_cleaned = {v: k for k, v in column_mapping.items()}
    for col in original_columns:
        if col not in original_to_cleaned:
            original_to_cleaned[col] = col

    input_df = input_df.withColumn("_LOAD_DTS", F.current_timestamp())
    input_df = input_df.withColumn("_LOAD_DATE", F.current_date())
    input_df = input_df.withColumn("_SOURCE_FILE_BYTES", F.col("_metadata.file_size"))
    input_df = input_df.withColumn(
        "_SOURCE_FILE_MODIFIED", F.col("_metadata.file_modification_time")
    )
    input_df = input_df.withColumn("_SOURCE_FILE_NAME", F.col("_metadata.file_name"))

    ingest_ts_col = None
    if ingest_timestamp_column and ingest_timestamp_column in original_to_cleaned:
        ingest_ts_col = original_to_cleaned[ingest_timestamp_column]

    if ingest_ts_col and ingest_ts_col in input_df.columns:
        if ingest_date_format:
            input_df = input_df.withColumn(
                "_INGEST_DTS",
                F.to_timestamp(F.col(ingest_ts_col), ingest_date_format),
            )
        else:
            input_df = input_df.withColumn("_INGEST_DTS", F.col(ingest_ts_col).cast("timestamp"))
        input_df = input_df.withColumn("_INGEST_DATE", F.col("_INGEST_DTS").cast("date"))
    else:
        input_df = input_df.withColumn(
            "_INGEST_DATE",
            F.to_date(
                F.regexp_replace(
                    F.substring_index(F.col("_SOURCE_FILE_NAME"), "_", -1),
                    r"\.[^.]+$",
                    "",
                ),
                "yyyyMMdd",
            ),
        )
        input_df = input_df.withColumn(
            "_INGEST_DTS",
            F.when(
                F.col("_INGEST_DATE").isNotNull(),
                F.col("_INGEST_DATE").cast("timestamp"),
            ).otherwise(F.lit(None).cast("timestamp")),
        )

    query = (
        input_df.writeStream.option("mergeSchema", "true")
        .option("checkpointLocation", autoloader_path)
        .trigger(availableNow=True)
        .toTable(table_path)
    )
    query.awaitTermination()

    try:
        schema = spark.sql(f"DESCRIBE {table_path}").collect()
        cols = [row.col_name for row in schema]
        if "_temp" in cols and len(cols) > 1:
            spark.sql(f"ALTER TABLE {table_path} DROP COLUMN _temp")
    except Exception:
        pass

    print(f"Copper table complete: {table_path}")
