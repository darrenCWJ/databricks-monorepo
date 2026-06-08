"""Gold layer — monthly snapshot aggregation from silver.

Creates point-in-time snapshots at month-end boundaries with fiscal year
alignment (April start). Supports period-based and current-latest modes.
"""

from pyspark.sql import SparkSession

from de_toolbox.delta import save_df_to_delta_with_column_mapping
from de_toolbox.snapshot import create_monthly_snapshot


def create_gold_table(
    spark: SparkSession,
    env: str,
    table_name: str,
    full_reload: bool,
    config_dict: dict,
) -> None:
    """Create gold-layer monthly snapshot from silver table.

    Args:
        spark: Active SparkSession.
        env: Environment (dev, stg, prd).
        table_name: Table name (without prefix).
        full_reload: Currently unused — gold always overwrites.
        config_dict: Config dict with keys:
            - domain, subdomain
            - gold: {primary_keys, order_by_column, snapshot_type,
                     report_date_adjustment}
    """
    domain = config_dict.get("domain", "default_domain")
    subdomain = config_dict.get("subdomain", "default")
    gold_config = config_dict.get("gold", {})

    snapshot_type = gold_config.get("snapshot_type", "period")
    report_date_adjustment = gold_config.get("report_date_adjustment", 0)
    primary_keys = gold_config.get("primary_keys", None)
    order_by_column = gold_config.get("order_by_column", "_INGEST_DATE")

    if not primary_keys and snapshot_type == "period":
        raise ValueError("primary_keys required in gold config for snapshot_type='period'")

    if snapshot_type == "period":
        table_prefix = "gold_snap_mth"
    else:
        table_prefix = "gold_snap_lst"

    silver_table = f"{domain}_{env}.{subdomain}.silver_{table_name}"
    gold_table = f"{domain}_{env}.{subdomain}.{table_prefix}_{table_name}"

    print(f"Gold: {silver_table} -> {gold_table}")

    df = spark.table(silver_table)

    snapshot_df = create_monthly_snapshot(
        spark,
        df,
        primary_keys,
        order_by_column,
        snapshot_type,
        report_date_adjustment,
    )

    save_df_to_delta_with_column_mapping(
        spark, snapshot_df, gold_table, save_data=True, save_mode="overwrite"
    )
    print(f"Gold table complete: {gold_table}")
