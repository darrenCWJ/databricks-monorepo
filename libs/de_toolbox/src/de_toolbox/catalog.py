"""Catalog and path resolution utilities.

get_catalog and get_repo_path are pure functions (no spark).
get_tables requires spark.
"""

from datetime import datetime, timedelta

import pytz
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def get_catalog(project: str, env: str) -> str:
    """Resolve Unity Catalog name from project + environment.

    Args:
        project: Project identifier (e.g., "finance", "hcm").
        env: Environment — must be one of "dev", "uat", "stg", "prd".

    Returns:
        Catalog name in format "{project}_{env}".

    Raises:
        ValueError: If env is not a valid environment.
    """
    valid_envs = ("dev", "uat", "stg", "prd")
    if env not in valid_envs:
        raise ValueError(f"Catalog Env: {env} is invalid! Must be one of {valid_envs}")
    return f"{project}_{env}"


def get_repo_path(project: str, debug: str | None, folder: str = "base") -> str:
    """Resolve the metadata folder path within a Databricks Workspace Repo.

    Args:
        project: Project identifier.
        debug: If set, uses this as the Repos subfolder (for dev overrides).
        folder: Metadata subfolder name (default "base").

    Returns:
        Absolute workspace path to the metadata folder.
    """
    if debug:
        return f"/Workspace/Repos/{debug}/de_{project}/metadata/{folder}"
    if project == "toolbox":
        return f"/Workspace/Repos/shared/de_{project}/metadata/{folder}"
    return f"../metadata/{folder}"


def get_tables(
    spark: SparkSession, catalog: str, compute_all: bool = False, env: str = "prd"
) -> list:
    """Get all tables within a catalog's bronze schema.

    Iterates through accessible catalogs and returns tables from the bronze
    schema. By default only returns tables modified in the last 12 hours.

    Args:
        spark: Active SparkSession.
        catalog: Catalog name to query.
        compute_all: If True, return all tables regardless of last_altered time.
        env: Environment (default "prd").

    Returns:
        List of fully qualified table paths (catalog.schema.table).
    """
    schema = "bronze"

    if compute_all:
        all_tables = spark.read.table(f"{catalog}.information_schema.tables").filter(
            F.col("table_schema") == schema
        )
    else:
        current_time = datetime.now(pytz.timezone("Asia/Singapore"))
        time_threshold = current_time - timedelta(hours=12)
        all_tables = (
            spark.read.table(f"{catalog}.information_schema.tables")
            .where(F.col("table_schema") == schema)
            .where(F.col("last_altered") >= time_threshold)
        )

    return (
        all_tables.select(
            F.concat(
                F.col("table_catalog"),
                F.lit("."),
                F.col("table_schema"),
                F.lit("."),
                F.col("table_name"),
            ).alias("full_table_name")
        )
        .toPandas()["full_table_name"]
        .tolist()
    )
