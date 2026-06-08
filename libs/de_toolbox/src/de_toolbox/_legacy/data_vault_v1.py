import json

from de_toolbox.catalog import get_catalog, get_repo_path
from de_toolbox.permissions import (
    change_securable_object_owner,
    grant_securable_object_permission_in_dev,
    set_securable_object_tag,
)


def get_hub_sql(
    bronze_table_name,
    columns_as_str,
    hash_foreign_key,
    hash_primary_key,
    new_columns_str,
    new_primary_key_str,
    old_columns_str,
    old_primary_key_str,
    predicate,
    silver_table_name,
    table_source,
):

    query = f"""
    MERGE INTO silver.{silver_table_name} dest USING (
      SELECT
        MD5(CONCAT_WS('_', {new_primary_key_str})) AS {hash_primary_key},
        {new_columns_str},
        _LOAD_DTS,
        UPPER("{table_source}") AS _REC_SRC
      FROM (
        SELECT *
        FROM (
            SELECT
              {columns_as_str},
              ROW_NUMBER() OVER (PARTITION BY MD5(CONCAT_WS('_', {old_columns_str})) ORDER BY _LOAD_DTS ASC) AS _LOAD_RANK,
              _LOAD_DTS
            FROM
              bronze.{bronze_table_name}
            {predicate}
        )
        WHERE _LOAD_RANK = 1
      )
    ) src ON src.{hash_primary_key} = dest.{hash_primary_key}
    WHEN NOT MATCHED THEN
    INSERT
      *;
    """
    return [query]


def get_link_sql(
    bronze_table_name,
    columns_as_str,
    hash_foreign_key,
    hash_primary_key,
    new_columns_str,
    new_primary_key_str,
    old_columns_str,
    old_primary_key_str,
    predicate,
    silver_table_name,
    table_source,
):

    query = f"""
    MERGE INTO silver.{silver_table_name} dest USING (
      SELECT
        MD5(CONCAT_WS('_', {new_primary_key_str})) AS {hash_primary_key},
        {hash_foreign_key},
        {new_columns_str},
        _LOAD_DTS,
        UPPER("{table_source}") AS _REC_SRC
      FROM (
        SELECT *
        FROM (
          SELECT
              {columns_as_str},
              ROW_NUMBER() OVER (PARTITION BY MD5(CONCAT_WS('_', {old_columns_str})) ORDER BY _LOAD_DTS ASC) AS _LOAD_RANK,
              _LOAD_DTS
            FROM
              bronze.{bronze_table_name}
            {predicate}
        )
        WHERE _LOAD_RANK = 1
      )
    ) src ON src.{hash_primary_key} = dest.{hash_primary_key}
    WHEN NOT MATCHED THEN
    INSERT
      *;
    """
    return [query]


def get_satellite_sql(
    bronze_table_name,
    columns_as_str,
    hash_foreign_key,
    hash_primary_key,
    new_columns_str,
    new_primary_key_str,
    old_columns_str,
    old_primary_key_str,
    predicate,
    silver_table_name,
    table_source,
):

    columns_as_str_max = ", ".join(
        [f"MAX({x.split(' AS ')[0]}) AS {x.split(' AS ')[1]}" for x in columns_as_str.split(", ")]
    )
    query1 = f"""
    CREATE OR REPLACE TEMPORARY VIEW tmp_{silver_table_name} AS (
      SELECT
        * EXCEPT({new_primary_key_str}, _LEAD_HASH_DIFF)
      FROM (
        SELECT
            *,
            LEAD(_HASH_DIFF, -1, "") OVER (PARTITION BY {hash_primary_key} ORDER BY _LOAD_DTS) AS _LEAD_HASH_DIFF
        FROM (
          SELECT
            MD5(CONCAT_WS('_', {new_primary_key_str})) AS {hash_primary_key},
            MD5(CONCAT_WS('_', {new_columns_str})) AS _HASH_DIFF,
            {new_columns_str}, 
            _LOAD_DTS,
            UPPER('{table_source}') AS _REC_SRC
          FROM (
            SELECT
              {columns_as_str_max}, _LOAD_DTS
            FROM
              bronze.{bronze_table_name}
            {predicate}
            GROUP BY {old_primary_key_str}, _LOAD_DTS
          )
        )
      )
      WHERE _HASH_DIFF != _LEAD_HASH_DIFF
    );
    """

    query2 = f"""
    MERGE INTO silver.{silver_table_name} dest 
    USING (
        SELECT tmp_src.*
        FROM tmp_{silver_table_name} tmp_src
        WHERE NOT EXISTS (
            SELECT 1
            FROM (
                SELECT *
                FROM (
                    SELECT *, 
                        ROW_NUMBER() OVER (PARTITION BY {hash_primary_key} ORDER BY _LOAD_DTS DESC) AS _LOAD_RANK
                    FROM silver.{silver_table_name}
                ) ranked
                WHERE _LOAD_RANK = 1
            ) tmp_dest 
            WHERE tmp_src.{hash_primary_key} = tmp_dest.{hash_primary_key} 
            AND tmp_src._HASH_DIFF = tmp_dest._HASH_DIFF
        )
    ) src 
    ON dest.{hash_primary_key} = src.{hash_primary_key} AND src._HASH_DIFF = dest._HASH_DIFF AND src._LOAD_DTS = dest._LOAD_DTS
    WHEN NOT MATCHED THEN
    INSERT
      *;
    """
    return [query1, query2]


def get_columns_mapping(meta):

    # Read Bronze table for data type
    dt_mapping = {}
    table_name = meta["table_name"]
    dt_mapping = (
        spark.sql(f"DESCRIBE TABLE bronze.{table_name}")
        .toPandas()
        .set_index("col_name")
        .to_dict()["data_type"]
    )

    mapping = meta["column_rename"]
    # Custom data type re-mapping
    adhoc_dt_mapping = meta["datatype_remap"]
    # Reverse dictionary to find original name
    r_mapping = {v: k for k, v in mapping.items()}

    # Get columns required for Hub, Link, Satellite
    columns = (
        [row["columns"] for row in meta["hub"]]
        + [row["columns"] for row in meta["link"]]
        + [row["columns"] for row in meta["satellite"]]
    )
    columns = [item for sublist in columns for item in sublist]
    columns = set(columns)

    # Format columns with new name and data type
    column_mapping = {}
    for k in columns:
        # Case 1: In adhoc datatype mapping and in reverse mapping
        # Case 2: In adhoc datatype mappping and not in reverse mapping
        # Case 3: Not in adhoc datatype mapping and in reverse mapping
        # Case 4: Not in adhoc datatype mapping and not in reverse mapping

        if k in adhoc_dt_mapping:
            cast = r_mapping[k] if k in r_mapping else k
            v = r_mapping[k] if k in r_mapping else k
            for c in adhoc_dt_mapping[k]:
                cast = f"{cast} as {c}"
                cast = f"CAST({cast})"
            column_mapping[k] = {
                "as": f"{cast} AS {k}",
                "dt": adhoc_dt_mapping[k][-1],
                "v": v,
            }
        else:
            if k in r_mapping:
                column_mapping[k] = {
                    "as": f"{r_mapping[k]} AS {k}",
                    "dt": dt_mapping.get(r_mapping[k]),
                    "v": r_mapping[k],
                }
            else:
                column_mapping[k] = {
                    "as": f"{k} AS {k}",
                    "dt": dt_mapping.get(k),
                    "v": k,
                }

    if meta["verbose"]:
        print(column_mapping)

    return column_mapping


def create_or_truncate_tables(metadata, meta, truncate, catalog):

    # Create schema
    spark.sql("CREATE SCHEMA IF NOT EXISTS silver")

    # Get column rename / data type
    column_mapping = get_columns_mapping(meta)
    validate_columns(column_mapping)

    for key in meta:
        # Drop non-vault metadata
        if key not in ["hub", "link", "satellite"]:
            continue

        # Multi-tables for Hub, Link, Satellite
        for row in meta[key]:
            table_prefix = meta["table_lookup"][key]
            table_name = f"{table_prefix}_{row['table_name']}"

            columns = row["columns"]
            primary_key = sorted(row["primary_key"])
            hash_primary_key = "Hash" + "".join(primary_key)
            table_meta = {k: column_mapping[k] for k in columns}

            meta_columns = []
            if key == "hub":
                columns = ", ".join([k + " " + v["dt"] for k, v in table_meta.items()])
            if key == "link":
                foreign_key = [
                    f"Hash{''.join(sorted(x))} STRING" if isinstance(x, list) else f"Hash{x} STRING"
                    for x in row["foreign_key"]
                ]
                columns = ""
                columns = ", ".join(foreign_key) + ", "
                columns += ", ".join([k + " " + v["dt"] for k, v in table_meta.items()])
            if key == "satellite":
                columns = ", ".join(
                    [k + " " + v["dt"] for k, v in table_meta.items() if k not in primary_key]
                )
                meta_columns += ["_HASH_DIFF STRING"]

            meta_columns += ["_LOAD_DTS TIMESTAMP", "_REC_SRC STRING"]
            meta_columns = ", ".join(meta_columns)

            # Generate Create Table SQL
            query = f"""
            CREATE TABLE IF NOT EXISTS silver.{table_name} (
            {hash_primary_key} STRING, {columns}, {meta_columns})
            """

            # Execute Command
            result = spark.sql(query)

            # Assign tag
            set_securable_object_tag(spark, metadata, row, f"silver.{table_name}")

            # Change owner
            change_securable_object_owner(
                spark,
                metadata,
                row,
                catalog.split("_")[0],
                catalog.split("_")[-1],
                f"silver.{table_name}",
            )

            # Change permission
            grant_securable_object_permission_in_dev(
                spark,
                metadata,
                catalog.split("_")[0],
                catalog.split("_")[-1],
                f"silver.{table_name}",
            )

            # Truncate for Full Reload
            if truncate:
                query = f"""DELETE FROM silver.{table_name} WHERE _REC_SRC = "{meta["source"].upper()}" """
                spark.sql(query)

            # Print
            if meta["verbose"]:
                print(query)


def update_table(meta, truncate):
    for table_type in ["hub", "link", "satellite"]:
        bronze_table_name = meta["table_name"]
        table_prefix = meta["table_lookup"][table_type]
        table_source = meta["source"]
        column_mapping = get_columns_mapping(meta)

        for row in meta[table_type]:
            silver_table_name = f"{table_prefix}_{row['table_name']}"

            # Format Primary Key
            primary_key = sorted(row["primary_key"])
            hash_primary_key = "Hash" + "".join(primary_key)
            old_primary_key_str = ", ".join([column_mapping[x]["v"] for x in primary_key])
            new_primary_key_str = ", ".join(primary_key)

            # Format Foreign Key
            hash_foreign_key = []
            if "foreign_key" in row:
                for x in row["foreign_key"]:
                    if not isinstance(x, list):
                        x = [x]
                    x = sorted(x)
                    x = f"MD5(CONCAT_WS('_', {','.join(x)})) AS Hash{''.join(x)}"
                    hash_foreign_key.append(x)
                hash_foreign_key = ", ".join(hash_foreign_key)

            # Format Columns
            columns = row["columns"]
            columns_as_str = ", ".join([column_mapping[x]["as"] for x in columns])
            old_columns_str = ", ".join([column_mapping[x]["v"] for x in columns])
            new_columns_str = ", ".join(columns)

            # Full Historical Load
            predicate = ""
            if not truncate:
                predicate = (
                    f"WHERE _INGEST_DTS = (SELECT MAX(_INGEST_DTS) FROM bronze.{bronze_table_name})"
                )

            kwargs = {
                "bronze_table_name": bronze_table_name,
                "columns_as_str": columns_as_str,
                "hash_foreign_key": hash_foreign_key,
                "hash_primary_key": hash_primary_key,
                "new_columns_str": new_columns_str,
                "new_primary_key_str": new_primary_key_str,
                "old_columns_str": old_columns_str,
                "old_primary_key_str": old_primary_key_str,
                "predicate": predicate,
                "silver_table_name": silver_table_name,
                "table_source": table_source,
            }

            if table_type == "hub":
                query = get_hub_sql(**kwargs)
            if table_type == "link":
                query = get_link_sql(**kwargs)
            if table_type == "satellite":
                query = get_satellite_sql(**kwargs)

            # Execute command
            for q in query:
                result = spark.sql(q)

            # Print
            if meta["verbose"]:
                print(query)
                print(result.show())


def validate_columns(column_mapping):
    cols = [column_mapping[k]["as"] for k in column_mapping.keys() if not column_mapping[k]["dt"]]
    if len(cols) != 0:
        print(cols)
        raise Exception("Invalid columns detected in metadata.json")


def create_silver(
    _spark, project, metadata_name, env, first_load=False, full_reload=False, debug=None
):
    global spark
    if project == "toolbox":
        catalog_name = get_catalog("test", env)
    else:
        catalog_name = get_catalog(project, env)

    base_path = get_repo_path(project, debug)
    metadata_path = f"{base_path}/{metadata_name}.json"

    with open(metadata_path) as read_file:
        metadata = json.load(read_file)

    spark = _spark
    # Convert param to True/False
    full_reload = spark.sql(f"select '{full_reload}' is true").collect()[0][0]
    first_load = spark.sql(f"select '{first_load}' is true").collect()[0][0]

    spark.sql(f"USE CATALOG {catalog_name}")
    meta = metadata["silver"]
    meta["table_lookup"] = {"hub": "hub", "link": "lnk", "satellite": "sat"}
    meta["source"] = metadata["source"]
    meta["table_name"] = metadata["table_name"]
    meta["verbose"] = metadata.get("verbose")

    if first_load or full_reload:
        create_or_truncate_tables(metadata, meta, full_reload, catalog_name)

    update_table(meta, full_reload)

    # if project != "toolbox":
    #     grant_permission(spark, metadata, env)
