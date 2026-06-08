import builtins
import json
import re
from calendar import month_abbr
from datetime import *

import pytz
from dateutil.parser import ParserError, parse
from pyspark.sql import functions as F
from pyspark.sql.functions import *
from pyspark.sql.types import DateType

from de_toolbox.catalog import get_catalog, get_repo_path
from de_toolbox.permissions import (
    change_securable_object_owner,
    grant_securable_object_permission_in_dev,
    set_securable_object_tag,
)


def drop_columns(df, columns):
    # Iterate over the list of columns to be dropped
    for column in columns:
        # Drop the column from the DataFrame
        df = df.drop(column)
    # Return the DataFrame after dropping the specified columns
    return df


def byot(df, configs, first_load):
    for config in configs:
        # Custom for First Load vs Non First Load
        if "first_load" in config and first_load != config["first_load"]:
            continue
        f = eval(config["function"])
        args = []
        for arg in config["args"]:
            if isinstance(arg, list):
                args.append(eval(arg[0])(arg[1]))
            else:
                args.append(arg)
        df = df.withColumn(config["new_column_name"], f(*args))
    return df


def get_date_from_string(text=[], date_meta=None):
    tz = pytz.timezone("Singapore")
    date_meta = {} if date_meta is None else date_meta
    if not isinstance(date_meta, dict):
        return [datetime.now(tz=tz).date()]

    text = text.lower()
    text = [x for x in re.sub(r"[^a-zA-Z0-9]", " ", text).split()]
    start_index = date_meta.get("start_index", 0)
    end_index = date_meta.get("end_index", -len(text))
    months = [x.lower() for x in month_abbr if x]
    text = text[start_index:]
    text = text[:-end_index]
    text = [
        x
        for x in text
        if x.isdigit()
        or any([month in x for month in months])
        or re.findall(r"[0-9]+(?:st|[nr]d|th)", x)
    ]
    day_first = date_meta.get("dayfirst", False)
    year_first = date_meta.get("yearfirst", False)
    date_index = date_meta.get("date_index", [0])
    date_count = len(date_index)

    def helper(n):
        k, m = divmod(len(text), n)
        dates = list(
            text[i * k + builtins.min(i, m) : (i + 1) * k + builtins.min(i + 1, m)]
            for i in range(n)
        )
        now = datetime.now()
        out = []
        try:
            for i in date_index:
                dt = "-".join(dates[i])
                dt = parse(
                    dt,
                    fuzzy=True,
                    dayfirst=day_first,
                    yearfirst=year_first,
                    default=datetime(now.year, now.month, 1),
                ).date()
                out.append(dt)
            return out
        except ParserError:
            return None

    result = helper(date_count)

    if result:
        return result
    elif "date_index" not in date_meta and len(text) in [4, 6]:
        return helper(2)

    return None


def format_validator(meta):
    # Validates if the file format is one of these: CSV, Json, Parquet, Avro
    file_format = meta["bronze"]["file_format"]
    accept_format = ["csv", "json", "parquet", "avro"]
    if file_format.lower() not in accept_format:
        print("File format must be in csv, json, parquet or avro")
    else:
        return True


def upper_camel_case(string):
    if " " in string:
        string = string.title()
    string = string[0].upper() + string[1:]
    return (
        string.replace("%", "Percent")
        .replace(".", "")
        .replace(" ", "")
        .replace("\n", "")
        .replace("\t", "")
    )


def remove_invalid_chars(df):
    for cols in df.columns:
        if "." in cols:
            df = df.withColumnRenamed(cols, upper_camel_case(cols))

    return df.select(
        [
            col(x).alias(re.sub(r"[^a-zA-Z0-9]", "", upper_camel_case(x)))
            if not x.startswith("_")
            else x
            for x in df.columns
        ]
    )


# def remove_invalid_chars_v2(df):
#     column_mapping = {}
#     column_counter = {}
#     columns = sorted(df.columns)

#     for c in columns:
#         if c.startswith("_"):
#             column_mapping[c] = c
#             continue

#         tmp_name = re.sub(r"[^a-zA-Z0-9]", "", upper_camel_case(c))
#         clean_name = tmp_name

#         # Increment duplicated clean column names
#         counter = column_counter.get(tmp_name, -1) + 1
#         if tmp_name in column_counter:
#             clean_name += str(counter)

#         column_mapping[c] = clean_name
#         column_counter[tmp_name] = counter

#     return df.select(
#         [
#             col(x).alias(column_mapping[x])
#             for x in df.columns
#         ]
#     )


def remove_whitespace(df):
    return df.select(
        [
            when(col(c) == " ", None)
            .otherwise(
                when(col(c).endswith("\\r"), trim(regexp_replace(col(c), "\\\\r", ""))).otherwise(
                    when(
                        col(c).endswith("\\n"),
                        trim(regexp_replace(col(c), "\\\\n", "")),
                    ).otherwise(trim(col(c)))
                )
            )
            .alias(c)
            if dt == "string"
            else c
            for c, dt in df.dtypes
        ]
    )


def get_date(row):
    row = row.replace("%20", "_")
    get_date = get_date_from_string(row)
    get_date_str = str(get_date).strip("[]").replace("datetime.date", "").strip("()")
    file_dts = datetime.strptime(get_date_str, "%Y, %m, %d").date()

    return file_dts


def get_min_load_date(catalog, table_name, historical_load, first_load):
    if first_load:
        suffix = "/history"
    else:
        suffix = ""
    try:
        base_df = spark.read.table(f"{catalog}.bronze.{table_name}")
        if not historical_load:
            return False, base_df.agg({"_INGEST_DTS": "min"}).collect()[0][0].strftime(
                "%Y-%m-%d %H:%M:%S"
            ) + suffix
    except Exception as e:
        print(str(e))
        pass
    return True, datetime.now().strftime("%Y-%m-%d %H:%M:%S") + suffix


def read_autoloader(meta, catalog, env, historical_load, first_load):

    # Check if its validated
    if format_validator(meta):
        project = meta["project"]
        table_name = meta["table_name"]
        base_path = f"s3://sst-s3-gvt-databricks-{env}-autoloader"
        connector = meta["bronze"]["connector"]
        table_path_prefix = meta.get("bronze", {}).get("table_path_prefix", None)

        # First Load for manually loaded data in Volumes
        if connector == "Volume" and table_path_prefix:
            read_path = f"dbfs:/Volumes/{catalog}/bronze/{table_path_prefix}{table_name}"
        elif connector == "Volume" or first_load:
            read_path = f"dbfs:/Volumes/{catalog}/bronze/{table_name}"
        else:
            read_path = f"s3://sst-s3-gvt-databricks-{env}-landing/{project}/{table_name}"

        file_format = meta["bronze"]["file_format"]
        pk_list = meta["bronze"]["pk"]
        date_list = meta["bronze"]["column_datetype"]
        additional_options = meta.get("bronze", {}).get("additional_options", {})

        # Set PK/Date to STRING datatype
        string_dt = ",".join([col + " STRING" for col in set(pk_list + date_list)])
        string_dt = string_dt if string_dt else None

        if historical_load:
            options = {"cloudFiles.useIncrementalListing": "false"}
        else:
            options = {"ignoreMissingFiles": True}

        df = (
            spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", f"{file_format}")
            .option("quote", '"')
            .option("escape", '"')
            .option("multiLine", "true")
            .option("header", True)
            .option("cloudFiles.schemaHints", string_dt)
            .option(
                "cloudFiles.schemaLocation",
                f"{base_path}/{project}/{table_name}/{ingest_dts_min_date}",
            )
            .option("cloudFiles.inferColumnTypes", True)
            .option("cloudFiles.allowOverwrites", False)
        )

        for k, v in options.items():
            df = df.option(k, v)

        # Add additional options only if they exist and are not empty
        if additional_options and len(additional_options) > 0:
            df = df.options(**additional_options)

        try:
            df = (
                df.load(f"{read_path}")
                .select(
                    "*",
                    col("_metadata.file_name").alias("_file_name"),
                    col("_metadata.file_path").alias("_file_path"),
                )
                .transform(lambda df: remove_invalid_chars(df))
                .transform(lambda df: remove_whitespace(df))
            )
        except Exception as e:
            if "UC_VOLUME_NOT_FOUND" in str(e):
                return
            else:
                raise e
        return df


def write_autoloader(meta, catalog, bronze_schema, env, historical_load, first_load):
    # Storage trigger to trigger whenever there is a change in row
    df = read_autoloader(meta, catalog, env, historical_load, first_load)

    if not df:
        return

    table_name = meta["table_name"]
    base_path = f"s3://sst-s3-gvt-databricks-{env}-autoloader"
    project = meta["project"]
    effectivedate = meta["bronze"]["effective_date"]
    current_timestamp = datetime.today()
    col_datetype = meta["bronze"]["column_datetype"]

    map_flg = meta["bronze"]["mapping"]["flg"]
    if map_flg == "y":
        ref_table = meta["bronze"]["mapping"]["ref_table"]
        ref_table = meta["bronze"]["mapping"]["catalog"] + f"_{env}." + ref_table
        ref_pk = meta["bronze"]["mapping"]["pk"]
        hash_pk = "Hash" + ref_pk
        prefix = meta["bronze"]["mapping"]["prefix"]
        add_column = meta["bronze"]["mapping"]["new_column"]
        condition = meta["bronze"]["mapping"]["condition"]

    # Get File Date or Effective Date
    date_convert_udf = udf(get_date, DateType())
    df = df.withColumn("_LOAD_DTS", date_convert_udf(df["_file_name"]))

    # Add custom transformation
    df = byot(df, meta["bronze"].get("transform", []), first_load)

    if effectivedate:
        df = df.withColumn("_LOAD_DTS", to_date(F.col(f"{effectivedate}")))

    # Drop _File_name
    df = df.drop("_file_name")
    df = df.drop("_file_path")

    select_expr = [
        to_date(col(cols)).alias(cols) if cols in col_datetype else col(cols)
        for cols, type in df.dtypes
    ]

    if ingest_dts_flag:
        df_final = df.select(*select_expr).withColumn(
            "_INGEST_DTS", to_timestamp(lit(ingest_dts_min_date.split("/")[0]))
        )
    else:
        df_final = df.select(*select_expr).withColumn("_INGEST_DTS", F.current_timestamp())

    if map_flg == "y":
        gold_tbl = spark.table(f"{ref_table}").select(
            f"{add_column}", upper(col(f"{ref_pk}")).alias(f"{ref_pk}")
        )
        df_final = (
            df_final.select(df_final["*"], upper(col(f"{ref_pk}")).alias(f"{ref_pk}1"))
            .drop(f"{ref_pk}")
            .withColumnRenamed(f"{ref_pk}1", f"{ref_pk}")
        )
        df_final = (
            df_final.join(gold_tbl, on=f"{ref_pk}", how="left")
            .select(f"{add_column}", df_final["*"])
            .distinct()
        )

        df_final = df_final.withColumn(f"{hash_pk}", F.crc32(col(f"{ref_pk}"))).select(["*"])
        df_final = df_final.withColumn(
            f"{add_column}",
            coalesce(f"{add_column}", F.concat(F.lit(f"{prefix}"), f"{hash_pk}")),
        )

    if historical_load:
        spark.sql(f"delete from {catalog}.{bronze_schema}.{table_name}")

    # Drop Unwanted Columns
    df_final = drop_columns(df_final, meta["bronze"].get("drop_column", []))

    df_final = df_final.writeStream.format("delta")

    df_final = (
        df_final.option("mergeSchema", "true")
        .option("checkpointLocation", f"{base_path}/{project}/{table_name}/{ingest_dts_min_date}")
        .trigger(availableNow=True)
        .table(f"{catalog}.{bronze_schema}.{table_name}")
        .awaitTermination()
    )

    # Assign tag
    set_securable_object_tag(spark, meta, meta["bronze"], f"{catalog}.{bronze_schema}.{table_name}")

    # Change owner
    change_securable_object_owner(
        spark, meta, meta["bronze"], project, env, f"{catalog}.{bronze_schema}.{table_name}"
    )

    # Change permission
    grant_securable_object_permission_in_dev(
        spark, meta, project, env, f"{catalog}.{bronze_schema}.{table_name}"
    )

    return df_final


def create_bronze(
    _spark, project, metadata_name, env, historical_load, first_load=False, debug=None
):
    global spark, ingest_dts_flag, ingest_dts_min_date
    if project == "toolbox":
        catalog = get_catalog("test", env)
    else:
        catalog = get_catalog(project, env)

    base_path = get_repo_path(project, debug)
    metadata_path = f"{base_path}/{metadata_name}.json"

    with open(metadata_path) as read_file:
        metadata = json.load(read_file)

    bronze_schema = "bronze"
    spark = _spark
    if "time_parser_policy" in metadata["bronze"]:
        spark.conf.set(
            "spark.sql.legacy.timeParserPolicy", metadata["bronze"]["time_parser_policy"]
        )

    # Convert param to True/False
    historical_load = spark.sql(f"select '{historical_load}' is true").collect()[0][0]
    first_load = spark.sql(f"select '{first_load}' is true").collect()[0][0]

    # Folder for Checkpoint & Schema location
    ingest_dts_flag, ingest_dts_min_date = get_min_load_date(
        catalog, metadata["table_name"], historical_load, first_load
    )

    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{bronze_schema}")
    df = write_autoloader(metadata, catalog, bronze_schema, env, historical_load, first_load)

    # if df and project != "toolbox":
    #     grant_permission(spark, metadata, env)
