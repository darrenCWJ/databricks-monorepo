from datetime import datetime

import requests
from pyspark.sql.functions import *

from de_databricks.housekeep.notify import *

######################################################
##   These functions are not ready for production   ##
##   and will be updated at a later date.           ##
######################################################


## catalog functions
def get_catalog_and_schema_info(limit=None):
    dfs = []
    list_of_catalogs = SESSION.get("unity-catalog/catalogs").json()["catalogs"]
    for i, row in enumerate(list_of_catalogs):
        if limit and i > limit:
            break
        if row["owner"] == "System user":
            continue
        catalog_name = row["full_name"]
        list_of_schemas = SESSION.get(
            "unity-catalog/schemas", json={"catalog_name": catalog_name}
        ).json()["schemas"]
        df = (
            spark.createDataFrame(list_of_schemas)
            .filter(col("owner") != "System user")
            .withColumn("updated_at", from_unixtime(col("updated_at") / 1000))
            .select(
                "catalog_name",
                col("name").alias("schema_name"),
                col("updated_at").alias("schema_updated_at"),
            )
        )
        dfs.append(df)
    return _reduce(lambda a, b: a.unionByName(b), dfs)


def get_table_or_volume_info(df, asset_type):
    result = []
    for row in df.collect():
        list_of_records = SESSION.get(
            f"unity-catalog/{asset_type}",
            json={
                "catalog_name": row["catalog_name"],
                "schema_name": row["schema_name"],
            },
        ).json()
        if asset_type not in list_of_records:
            continue
        for r in list_of_records[asset_type]:
            result.append(
                {
                    "owner": r["owner"],
                    "catalog_name": r["catalog_name"],
                    "schema_name": r["schema_name"],
                    "name": r["name"],
                    "full_name": r["full_name"],
                    "updated_at": r["updated_at"],
                    "asset_type": asset_type,
                }
            )
    return spark.createDataFrame(result).withColumn(
        "updated_at", from_unixtime(col("updated_at") / 1000)
    )


def delete_schema(df):
    granted = {}
    for record in df.collect():
        catalog_name = record["catalog_name"]
        if catalog_name == "databricks_llama_guard_model":
            continue
        if catalog_name not in granted:
            spark.sql(f"GRANT ALL PRIVILEGES ON CATALOG `{catalog_name}` TO metastore_admin")
            granted[catalog_name] = True
        for schema_name in record["schema_name"]:
            if DEBUG:
                continue
            spark.sql(f"ALTER SCHEMA `{catalog_name}`.`{schema_name}` SET OWNER TO metastore_admin")
            spark.sql(f"DROP SCHEMA `{catalog_name}`.`{schema_name}`")
            print(f"Deleted Schema: `{catalog_name}`.`{schema_name}`")


def delete_asset(df):
    granted = {}
    for record in df.collect():
        catalog_name = record["catalog_name"]
        if catalog_name == "databricks_llama_guard_model":
            continue
        if catalog_name not in granted:
            spark.sql(f"GRANT ALL PRIVILEGES ON CATALOG `{catalog_name}` TO metastore_admin")
            granted[catalog_name] = True
        if DEBUG:
            continue
        full_name = record["full_name"]
        try:
            asset_type = record["asset_type"].rstrip("s")
            spark.sql(f"ALTER `{asset_type}` `{full_name}` SET OWNER TO metastore_admin")
            spark.sql(f"DROP `{asset_type}` `{full_name}`")
            print(f"Deleted {asset_type}: `{full_name}`")
        except Exception:
            pass


def housekeep_catalog(limit=None):
    CATALOG_WHITELIST = ["automate_sandbox", "admin_sandbox", "training"]
    catalog_df = get_catalog_and_schema_info(limit)
    df = (
        catalog_df.join(
            get_table_or_volume_info(catalog_df, "tables").union(
                get_table_or_volume_info(catalog_df, "volumes")
            ),
            ["catalog_name", "schema_name"],
            how="left",
        )
        .withColumn(
            "updated_at",
            when(col("updated_at").isNull(), col("schema_updated_at")).otherwise(col("updated_at")),
        )
        .filter(datediff(current_date(), "updated_at") >= 90)
        .filter(~col("catalog_name").isin(CATALOG_WHITELIST))
    )

    asset_owner_df = (
        df.filter(col("owner").contains("@"))
        .groupby(lower("owner").alias("owner"))
        .agg(collect_list("full_name").alias("full_name"))
    )

    inactive_asset_owner_dict = {row["owner"]: row["full_name"] for row in asset_owner_df.collect()}

    ## notification only send in sandbox
    if MODE == "Normal" and not is_deletion_date() and ENVIRONMENT == "Sandbox":
        notify_asset_owners(inactive_asset_owner_dict, future_date=DEFAULT_DATE)

    if DEBUG and ENVIRONMENT == "Sandbox":
        flatten = lambda x: [
            i for sub in x for i in (flatten(sub) if isinstance(sub, list) else [sub])
        ]
        notify_asset_owners(
            {DEBUG_EMAIL: flatten(inactive_asset_owner_dict.values())}, future_date=DEFAULT_DATE
        )

    empty_catalog_df = (
        df.filter(col("asset_type").isNull())
        .groupby("catalog_name")
        .agg(collect_list("schema_name").alias("schema_name"))
    )

    if (
        is_deletion_date()
        and (DEFAULT_DATE is None or datetime.now() >= DEFAULT_DATE)
        and MODE == "Normal"
    ):
        if ENVIRONMENT == "Sandbox":
            delete_schema(empty_catalog_df)
            delete_asset(df)

    return df
