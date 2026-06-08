def wd_snapshot(spark, env, domain, subdomain, table, snapshot_type=""):
    silver_path = f"{domain}_{env}.{subdomain}.silver_{table}"
    mart_path = f"{domain}_{env}.{subdomain}.mart_wd_{table}"

    match snapshot_type:
        case "dtl":
            snapshot_df = spark.sql(f"""
                WITH ingest AS (
                    SELECT Accounting_Date, max(`_INGEST_DATE`) AS `_INGEST_DATE` FROM {silver_path}
                    GROUP BY Accounting_Date
                ),
                silver AS (SELECT * FROM {silver_path})
                SELECT * FROM silver
                INNER JOIN
                ingest USING (Accounting_Date, `_INGEST_DATE`)
            """)
        case _:
            snapshot_df = spark.sql(f"""
                SELECT * FROM {silver_path}
                WHERE _INGEST_DATE = (SELECT MAX(_INGEST_DATE) FROM {silver_path})
            """)

    snapshot_df = snapshot_df.drop("_LOAD_DTS", "Hash_Key")
    snapshot_df.createOrReplaceTempView("snapshot_temp")

    spark.sql(f"CREATE OR REPLACE TABLE {mart_path} AS SELECT * FROM snapshot_temp")
