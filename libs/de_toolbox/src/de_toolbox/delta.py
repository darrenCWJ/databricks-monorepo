"""Delta table write operations with column mapping support.

Handles append, overwrite, merge modes with schema evolution, legacy table
migration, validation, and permission preservation.
"""

from pyspark.sql import DataFrame, SparkSession


def save_df_to_delta_with_column_mapping(
    spark: SparkSession,
    df: DataFrame,
    table_path: str,
    save_data: bool = True,
    save_mode: str = "append",
    merge_keys: list[str] | None = None,
    merge_condition: str | None = None,
    migrate_legacy: bool = False,
    migrate_legacy_mode: str = "temp_table",
    validate: dict | None = None,
) -> tuple[DataFrame, dict]:
    """Save DataFrame to Delta table with column mapping enabled (id mode).

    Handles column cleaning for Parquet compatibility, table creation with
    column mapping, legacy table migration, and data validation.

    Args:
        spark: Active SparkSession.
        df: DataFrame to save.
        table_path: Fully qualified table path (catalog.schema.table).
        save_data: Whether to write data (default True).
        save_mode: "append", "merge", or "overwrite" (default "append").
        merge_keys: Original column names for merge primary keys.
        merge_condition: Custom SQL merge condition (overrides merge_keys).
        migrate_legacy: Auto-migrate tables without column mapping (default False).
        migrate_legacy_mode: "cache" or "temp_table" (default "temp_table").
        validate: Validation config dict with keys: "null", "distinct",
                  "distinct_count", "column_name".

    Returns:
        Tuple of (cleaned_df, column_mapping_dict).

    Raises:
        ValueError: For invalid params or legacy table without migration flag.
        RuntimeError: If migration or column mapping setup fails.
        AssertionError: If validation fails.
    """
    # Import the full implementation from the original source
    # This is a facade that preserves the exact behavior while standardizing the interface
    from de_toolbox._internal.delta_impl import _save_df_to_delta_with_column_mapping

    return _save_df_to_delta_with_column_mapping(
        spark=spark,
        df=df,
        table_path=table_path,
        save_data=save_data,
        save_mode=save_mode,
        merge_keys=merge_keys,
        merge_condition=merge_condition,
        migrate_legacy=migrate_legacy,
        migrate_legacy_mode=migrate_legacy_mode,
        validate=validate,
    )
