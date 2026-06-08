"""Bronze layer — flatten nested structs, add hash key, save with column mapping.

Reads from copper table, explodes complex arrays, flattens structs/maps,
adds SHA-256 hash key, and writes to bronze Delta table.
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, MapType, StructType

from de_toolbox.delta import save_df_to_delta_with_column_mapping
from de_toolbox.pipeline.column_cleaning import METADATA_COLUMNS


def create_bronze_table(
    spark: SparkSession,
    env: str,
    table_name: str,
    full_reload: bool,
    config_dict: dict,
    max_depth: int = 10,
) -> None:
    """Flatten copper data and write to bronze Delta table.

    Args:
        spark: Active SparkSession.
        env: Environment (dev, stg, prd).
        table_name: Table name (without prefix).
        full_reload: If True, overwrites bronze table.
        config_dict: Config dict with domain, subdomain, bronze keys.
        max_depth: Max recursion depth for nested struct flattening.
    """
    domain = config_dict.get("domain", "default_domain")
    subdomain = config_dict.get("subdomain", "default")

    copper_table = f"{domain}_{env}.{subdomain}.copper_{table_name}"
    bronze_table = f"{domain}_{env}.{subdomain}.bronze_{table_name}"

    is_new_load = False

    try:
        bronze_tables = (
            spark.sql(f"SHOW TABLES IN {domain}_{env}.{subdomain}")
            .filter(F.col("tableName") == f"bronze_{table_name}")
            .collect()
        )

        if bronze_tables and not full_reload:
            max_dts = spark.sql(f"SELECT MAX(_INGEST_DTS) as m FROM {bronze_table}").collect()[0][
                "m"
            ]

            if max_dts is not None:
                df = spark.sql(f"SELECT * FROM {copper_table} WHERE _INGEST_DTS > '{max_dts}'")
                if df.count() == 0:
                    print("No new records. Exiting.")
                    return
            else:
                df = spark.table(copper_table)
        else:
            is_new_load = not full_reload
            df = spark.table(copper_table)
    except Exception:
        df = spark.table(copper_table)
        is_new_load = True

    df = _process_dataframe(df, max_depth)
    df = _add_hash_key(df)

    all_cols = df.columns
    regular = sorted([c for c in all_cols if not c.startswith("_")])
    underscore = sorted([c for c in all_cols if c.startswith("_")])
    df = df.select(*(regular + underscore))

    save_mode = "overwrite" if (full_reload or is_new_load) else "append"

    save_df_to_delta_with_column_mapping(
        spark, df, bronze_table, save_data=True, save_mode=save_mode
    )
    print(f"Bronze table complete: {bronze_table}")


def _process_dataframe(df, max_depth, depth=0):
    """Recursively flatten structs and explode complex arrays."""
    if depth >= max_depth:
        return df

    schema = df.schema

    for field in schema.fields:
        if isinstance(field.dataType, ArrayType) and isinstance(
            field.dataType.elementType, (StructType, MapType)
        ):
            df = df.select("*", F.explode(F.col(field.name)).alias(f"{field.name}_item"))
            df = df.drop(field.name)
            return _process_dataframe(df, max_depth, depth + 1)

    has_structs = False
    select_cols = []
    for field in schema.fields:
        if isinstance(field.dataType, StructType):
            has_structs = True
            for nested in field.dataType.fields:
                select_cols.append(
                    F.col(f"{field.name}.{nested.name}").alias(f"{field.name}_{nested.name}")
                )
        else:
            select_cols.append(F.col(field.name))

    if has_structs:
        df = df.select(*select_cols)
        return _process_dataframe(df, max_depth, depth + 1)

    for field in schema.fields:
        if isinstance(field.dataType, MapType):
            df = df.select(
                "*",
                F.explode(F.col(field.name)).alias(f"{field.name}_key", f"{field.name}_value"),
            )
            df = df.drop(field.name)
            return _process_dataframe(df, max_depth, depth + 1)

    return df


def _add_hash_key(df, hash_column: str = "_HASH_KEY"):
    """Add SHA-256 hash of all non-metadata columns."""
    filtered_cols = [c for c in df.columns if c not in METADATA_COLUMNS]
    if not filtered_cols:
        raise ValueError("No columns available for hashing")

    dtypes = dict(df.dtypes)
    string_exprs = [
        F.to_json(F.col(c))
        if dtypes[c].startswith(("struct", "array", "map"))
        else F.col(c).cast("string")
        for c in filtered_cols
    ]

    return df.withColumn(hash_column, F.sha2(F.concat_ws("|", *string_exprs), 256))
