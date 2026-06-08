"""Silver layer — transform, rename, clean naming conventions, save.

Reads from bronze table, applies column renames, custom transforms (BYOT),
drops columns, enforces naming conventions, and writes to silver Delta table.
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from de_toolbox.delta import save_df_to_delta_with_column_mapping
from de_toolbox.pipeline.column_cleaning import clean_columns_aggressive


def create_silver_table(
    spark: SparkSession,
    env: str,
    table_name: str,
    full_reload: bool,
    config_dict: dict,
) -> None:
    """Transform bronze data and write to silver Delta table.

    Args:
        spark: Active SparkSession.
        env: Environment (dev, stg, prd).
        table_name: Table name (without prefix).
        full_reload: If True, overwrites silver table.
        config_dict: Config dict with keys:
            - domain, subdomain
            - silver: {column_naming_convention, rename_columns, transform, drop_columns}
    """
    domain = config_dict.get("domain", "default_domain")
    subdomain = config_dict.get("subdomain", "default")
    silver_config = config_dict.get("silver", {})

    bronze_table = f"{domain}_{env}.{subdomain}.bronze_{table_name}"
    silver_table = f"{domain}_{env}.{subdomain}.silver_{table_name}"

    is_new_load = False

    try:
        silver_tables = (
            spark.sql(f"SHOW TABLES IN {domain}_{env}.{subdomain}")
            .filter(F.col("tableName") == f"silver_{table_name}")
            .collect()
        )

        if silver_tables and not full_reload:
            max_dts = spark.sql(f"SELECT MAX(_INGEST_DTS) as m FROM {silver_table}").collect()[0][
                "m"
            ]

            if max_dts is not None:
                df = spark.sql(f"SELECT * FROM {bronze_table} WHERE _INGEST_DTS > '{max_dts}'")
                if df.count() == 0:
                    print("No new records. Exiting.")
                    return
            else:
                df = spark.table(bronze_table)
        else:
            is_new_load = not full_reload
            df = spark.table(bronze_table)
    except Exception:
        df = spark.table(bronze_table)
        is_new_load = True

    rename_columns = silver_config.get("rename_columns", {})
    if rename_columns:
        for old_name, new_name in rename_columns.items():
            if old_name in df.columns:
                df = df.withColumnRenamed(old_name, new_name)

    transforms = silver_config.get("transform", [])
    if transforms:
        df = _apply_transforms(df, transforms)

    drop_cols = silver_config.get("drop_columns", [])
    if drop_cols:
        existing = [c for c in drop_cols if c in df.columns]
        if existing:
            df = df.drop(*existing)

    naming = silver_config.get("column_naming_convention", "pascal")
    df, _ = clean_columns_aggressive(df, naming)

    all_cols = df.columns
    regular = sorted([c for c in all_cols if not c.startswith("_")])
    underscore = sorted([c for c in all_cols if c.startswith("_")])
    df = df.select(*(regular + underscore))

    save_mode = "overwrite" if (full_reload or is_new_load) else "append"

    save_df_to_delta_with_column_mapping(
        spark, df, silver_table, save_data=True, save_mode=save_mode
    )
    print(f"Silver table complete: {silver_table}")


def _apply_transforms(df, transforms: list[dict]):
    """Apply BYOT (Bring Your Own Transform) operations from config."""
    for config in transforms:
        func = getattr(F, config["function"])
        args = []
        for arg in config["args"]:
            if isinstance(arg, list):
                nested_func = getattr(F, arg[0])
                args.append(nested_func(arg[1]))
            elif isinstance(arg, str) and arg in df.columns:
                args.append(F.col(arg))
            else:
                args.append(arg)
        kwargs = config.get("kwargs", {})
        df = df.withColumn(config["new_column_name"], func(*args, **kwargs))
    return df
