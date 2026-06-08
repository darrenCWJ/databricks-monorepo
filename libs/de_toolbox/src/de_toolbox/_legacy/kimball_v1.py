import json

from de_toolbox.catalog import get_catalog, get_repo_path


def create_pit(metadata, env, catalog, silver_schema):
    project = metadata["project"]
    for m in metadata["pit"]:
        table_name = "pit_" + m["table_name"]
        hash_primary_key = m["primary_key"]
        satellites = m["satellites"]
        query = get_pit_query(silver_schema, catalog, table_name, hash_primary_key, satellites)
        spark.sql(query)


def get_pit_query(silver_schema, catalog, table_name, hash_primary_key, satellites):
    s1 = []
    s2 = []
    s3 = []
    for table in satellites:
        s1.append(f"SELECT {hash_primary_key}, _LOAD_DTS FROM {catalog}.{silver_schema}.{table}")
        s2.append(
            f"MAX({table}._LOAD_DTS) OVER (PARTITION BY LD.{hash_primary_key} ORDER BY LD._LOAD_DTS) AS {table}_LOAD_DTS"
        )
        s3.append(
            f"LEFT JOIN {catalog}.{silver_schema}.{table} {table} ON ({table}.{hash_primary_key} = LD.{hash_primary_key} AND {table}._LOAD_DTS = LD._LOAD_DTS)"
        )

    s1 = " UNION ".join(s1)
    s2 = ",".join(s2)
    s3 = " ".join(s3)

    query = f"""
    CREATE OR REPLACE VIEW {catalog}.{silver_schema}.{table_name} AS (
      WITH LOAD_DATES AS (
        {s1}
      )
      SELECT
       LD.{hash_primary_key},
       LD._LOAD_DTS,
       LEAD(LD._LOAD_DTS) OVER (PARTITION BY LD.{hash_primary_key} ORDER BY LD._LOAD_DTS) _LOAD_END_DTS,
       {s2}
      FROM LOAD_DATES LD
      {s3}
      ORDER BY {hash_primary_key}
    )
    """
    return query


# Create fact table based on link tables
def fact_tbl(metadata, dict, catalog, silver_schema, gold_schema):
    fact = metadata["fact"]

    for attributes in fact:
        lnk_tbl = attributes["lnk_reference"]
        sat_tbl = attributes["sat_reference"]
        tbl_name = attributes["table_name"]
        pk = attributes["pk"]
        scd_type = attributes["scd"]

        # Add prefix to table name
        prefix_tbl_name = "fact_" + tbl_name

        spark.sql(f"create table if not exists {catalog}.{gold_schema}.{prefix_tbl_name}")

        lnk_cols = (
            spark.sql(f"describe table {catalog}.{silver_schema}.{lnk_tbl}").toPandas().col_name
        )

        sat_hash_cols = []
        for sat_cols in sat_tbl:
            if len(sat_tbl) > 0:
                sat_cols = (
                    spark.sql(f"describe table {catalog}.{silver_schema}.{sat_cols}")
                    .toPandas()
                    .col_name
                )
                for sat_col in sat_cols:
                    if sat_col.startswith("Hash"):
                        sat_hash_cols.append(sat_col)

        lnk_hash_cols = []
        for lnk_col in lnk_cols:
            if lnk_col.startswith("Hash"):
                lnk_hash_cols.append(lnk_col)

        temp_lnk_hash = []
        for k in lnk_hash_cols:
            temp_name = "a." + k
            temp_lnk_hash.append(temp_name)

        # Strip list
        temp_lnk_str_cols = ", ".join(temp_lnk_hash)
        lnk_str_cols = ", ".join(lnk_hash_cols)
        sat_str_cols = ", ".join(sat_hash_cols)

        if len(sat_tbl) == 0:
            spark.sql(f"""
                replace table {catalog}.{gold_schema}.{prefix_tbl_name}
                as select * except({lnk_str_cols}, _rec_src) from {catalog}.{silver_schema}.{lnk_tbl} 
                """)
        elif len(sat_tbl) == 1:
            for k, v in enumerate(sat_tbl):
                spark.sql(f"""
                    replace table {catalog}.{gold_schema}.{prefix_tbl_name}
                    as select * except({dict[k + 1]}.{sat_str_cols}, {temp_lnk_str_cols}, {dict[k]}._load_dts, {dict[k]}._rec_src, {dict[k + 1]}._rec_src,{dict[k + 1]}._hash_diff) 
                    from {catalog}.{silver_schema}.{v} {dict[k + 1]} 
                    left join {catalog}.{silver_schema}.{lnk_tbl} {dict[k]} on {dict[k]}.{pk} = {dict[k + 1]}.{pk}
                    """)
        else:
            pass


# Create dimension table
def dim_single_sat(metadata, dict, env, catalog, silver_schema, gold_schema):
    dim = metadata["dimension"]

    lst = []
    for attributes in dim:
        bk = attributes["bk"]
        pk = attributes["pk"]
        hub = attributes["hub_reference"]
        num_of_join = len(attributes["sat_reference"])
        scd_type = attributes["scd"]
        tbl_name = attributes["table_name"]
        num_of_bk = len(attributes["bk"])

        if attributes["project"]:
            project_dim = attributes["project"]
            catalog_dim = get_catalog(project_dim, env)
        else:
            catalog_dim = catalog

        if num_of_bk > 1:
            bk_lst = []
            for k in bk:
                temp_name = "a." + k
                bk_lst.append(temp_name)

            # Strip list
            bk_str_cols = ", ".join(bk_lst)

        # Add prefix to table name
        prefix_tbl_name = "dim_" + tbl_name

        for k, v in enumerate(attributes["sat_reference"]):
            if num_of_join == 1:
                if scd_type == 1:
                    if num_of_bk == 1:
                        str_bk = bk[0].strip("[]")
                        query = f"select distinct(*) from (select {dict[k]}.{str_bk}, {dict[k + 1]}.* except ({dict[k + 1]}.{pk}, {dict[k + 1]}._hash_diff, {dict[k + 1]}._rec_src) from {catalog_dim}.{silver_schema}.{hub} {dict[k]} left join {catalog_dim}.{silver_schema}.{v} {dict[k + 1]} on {dict[k]}.{pk} = {dict[k + 1]}.{pk} where b._load_dts = ( select max(_load_dts) from {catalog_dim}.{silver_schema}.{v} {dict[k + 2]} where a.{pk} = {dict[k + 2]}.{pk}))"

                        spark.sql(
                            f"create table if not exists {catalog}.{gold_schema}.{prefix_tbl_name}"
                        )

                        spark.sql(f"""
                            replace table {catalog}.{gold_schema}.{prefix_tbl_name} as 
                            {query};
                            """)
                    else:
                        query = f"select distinct(*) from (select {bk_str_cols}, {dict[k + 1]}.* except ({dict[k + 1]}.{pk}, {dict[k + 1]}._hash_diff, {dict[k + 1]}._rec_src) from {catalog_dim}.{silver_schema}.{hub} {dict[k]} left join {catalog_dim}.{silver_schema}.{v} {dict[k + 1]} on {dict[k]}.{pk} = {dict[k + 1]}.{pk} where b._load_dts = ( select max(_load_dts) from {catalog_dim}.{silver_schema}.{v} {dict[k + 2]} where a.{pk} = {dict[k + 2]}.{pk}))"

                        spark.sql(
                            f"create table if not exists {catalog}.{gold_schema}.{prefix_tbl_name}"
                        )

                        spark.sql(f"""
                            replace table {catalog}.{gold_schema}.{prefix_tbl_name} as 
                            {query};
                            """)

                else:
                    if num_of_bk == 1:
                        str_bk = bk[0].strip("[]")
                        query = f"select  {dict[k]}.{str_bk}, {dict[k + 1]}.* except({dict[k + 1]}.{pk}, {dict[k + 1]}._hash_diff, {dict[k + 1]}._rec_src, {dict[k + 1]}._load_dts), {dict[k + 1]}._load_dts as _VALID_FROM, lead({dict[k + 1]}._load_dts) over(partition by {dict[k + 1]}.{pk} order by {dict[k + 1]}._load_dts) as _VALID_TO from {catalog_dim}.{silver_schema}.{hub} {dict[k]} left join {catalog_dim}.{silver_schema}.{v} {dict[k + 1]} on {dict[k]}.{pk} = {dict[k + 1]}.{pk}"

                        spark.sql(
                            f"create table if not exists {catalog}.{gold_schema}.{prefix_tbl_name}"
                        )

                        spark.sql(f"""
                            replace table {catalog}.{gold_schema}.{prefix_tbl_name} as 
                            {query};
                        """)
                    else:
                        query = f"select {bk_str_cols}, {dict[k + 1]}.* except({dict[k + 1]}.{pk},{dict[k + 1]}._hash_diff, {dict[k + 1]}._rec_src, {dict[k + 1]}._load_dts), {dict[k + 1]}._load_dts as _VALID_FROM, lead({dict[k + 1]}._load_dts) over(partition by {dict[k + 1]}.{pk} order by {dict[k + 1]}._load_dts) as _VALID_TO from {catalog_dim}.{silver_schema}.{hub} {dict[k]} left join {catalog_dim}.{silver_schema}.{v} {dict[k + 1]} on {dict[k]}.{pk} = {dict[k + 1]}.{pk}"

                        spark.sql(
                            f"create table if not exists {catalog}.{gold_schema}.{prefix_tbl_name}"
                        )

                        spark.sql(f"""
                            replace table {catalog}.{gold_schema}.{prefix_tbl_name} as 
                            {query};
                        """)


def dim_multiple_sats(metadata, dict, catalog, silver_schema, gold_schema):
    dim = metadata["dimension"]

    # Get table name with multiple sats
    sat_lst = []

    for i in range(len(dim)):
        sat_tbl = dim[i]["sat_reference"]
        if len(sat_tbl) >= 2:
            sat_lst.append(dim[i]["table_name"])

    # Get metadata with multiple sats
    multi_sats_meta = []
    for attributes in range(len(dim)):
        for sat_tbl_name in sat_lst:
            if sat_tbl_name == dim[attributes]["table_name"]:
                multi_sats_meta.append(dim[attributes])

    # Get BK and Hub table
    for k in range(len(multi_sats_meta)):
        bk = multi_sats_meta[k]["bk"]
        pk = multi_sats_meta[k]["pk"]
        hub = multi_sats_meta[k]["hub_reference"]
        sats = multi_sats_meta[k]["sat_reference"]
        scd_type = multi_sats_meta[k]["scd"]
        tbl_name = multi_sats_meta[k]["table_name"]
        pit = multi_sats_meta[k]["pit_tbl"]
        pit_list = []
        for name in sats:
            pit_dts = name + "_LOAD_DTS"
            pit_list.append(pit_dts)

        # Add prefix to table name
        prefix_tbl_name = "dim_" + tbl_name
        str_bk = bk[0].strip("[]")
        if scd_type == 1:
            # Get select statement
            for k, v in enumerate(sats):
                if k == 0:
                    select_query = f"select distinct(*) from (select {dict[k]}.{str_bk}, {dict[k + 1]}._load_dts as _VALID_FROM, {dict[k + 2]}.* except({pk}, _load_dts, _rec_src, _hash_diff), "
                else:
                    select_query1 = f"{dict[k + 2]}.* except({pk}, _load_dts, _rec_src, _hash_diff)"

                    select_query = select_query + select_query1

            # Get join statement
            for k, v in enumerate(sats):
                if k == 0:
                    join_query = f" from {catalog}.{silver_schema}.{hub} {dict[k]} left join {catalog}.{silver_schema}.{pit} {dict[k + 1]} on {dict[k]}.{pk} = {dict[k + 1]}.{pk} left join {catalog}.{silver_schema}.{sats[k]} {dict[k + 2]} on {dict[k]}.{pk} = {dict[k + 2]}.{pk} and b.{pit_list[k]} = {dict[k + 2]}._load_dts "

                else:
                    join_query2 = f"left join {catalog}.{silver_schema}.{sats[k]} {dict[k + 2]} on a.{pk} = {dict[k + 2]}.{pk} and {dict[k + 2]}._load_dts = b.{pit_list[k]} "
                    conditional_query = "where b._load_end_dts is null)"
                    join_query = join_query + join_query2

            query = select_query + join_query + conditional_query

            spark.sql(f"create table if not exists {catalog}.{gold_schema}.{prefix_tbl_name}")

            spark.sql(f"""
                replace table {catalog}.{gold_schema}.{prefix_tbl_name} as 
                {query};
                 """)

        else:
            for k, v in enumerate(sats):
                if k == 0:
                    select_query = f"select distinct(*) from (select {dict[k + 2]}.* except(HashEmployeeId, _load_dts, _hash_diff, _rec_src), {dict[k + 1]}._load_dts as _VALID_FROM, {dict[k + 1]}._load_end_dts as _VALID_TO, "
                else:
                    select_query1 = (
                        f"{dict[k + 2]}.* except(HashEmployeeId, _load_dts, _hash_diff, _rec_src), "
                    )

                    select_query = select_query + select_query1

            # Get join statement
            for k, v in enumerate(sats):
                if k == 0:
                    join_query = f"{dict[k]}.{str_bk} from {catalog}.{silver_schema}.{hub} {dict[k]} left join (select *, ROW_NUMBER() OVER (PARTITION BY {pk}, YEAR(_LOAD_DTS), MONTH(_LOAD_DTS) ORDER BY _LOAD_DTS DESC) AS _LOAD_RANK FROM {catalog}.{silver_schema}.{pit}) {dict[k + 1]} on {dict[k]}.{pk} = {dict[k + 1]}.{pk} left join {catalog}.{silver_schema}.{sats[k]} {dict[k + 2]} on {dict[k]}.{pk} = {dict[k + 2]}.{pk} and b.{pit_list[k]} = {dict[k + 2]}._load_dts"
                else:
                    join_query1 = f" left join {catalog}.{silver_schema}.{sats[k]} {dict[k + 2]} on a.{pk} = {dict[k + 2]}.{pk} and {dict[k + 2]}._load_dts = b.{pit_list[k]}"
                    conditional_query = " where _load_rank = 1)"
                    join_query = join_query + join_query1

            query = select_query + join_query + conditional_query

            spark.sql(f"create table if not exists {catalog}.{gold_schema}.{prefix_tbl_name}")

            spark.sql(f"""
                replace table {catalog}.{gold_schema}.{prefix_tbl_name} as 
                {query};
                 """)


def create_gold(_spark, project, metadata_name, env, debug=None):
    global spark
    dict = {0: "a", 1: "b", 2: "c", 3: "d", 4: "e", 5: "f", 6: "g", 7: "h", 8: "i", 9: "j", 10: "k"}

    if project == "toolbox":
        catalog = get_catalog("test", env)
    else:
        catalog = get_catalog(project, env)

    base_path = get_repo_path(project, debug, folder="gold")
    metadata_path = f"{base_path}/{metadata_name}.json"

    with open(metadata_path) as read_file:
        metadata = json.load(read_file)

    spark = _spark
    bronze_schema = "bronze"
    silver_schema = "silver"
    gold_schema = "gold"

    dim = metadata["dimension"]
    fact = metadata["fact"]

    # Create schema
    spark.sql(f"create schema if not exists {catalog}.{gold_schema}")

    # PIT
    create_pit(metadata, env, catalog, silver_schema)

    # Dimension
    dim_single_sat(metadata, dict, env, catalog, silver_schema, gold_schema)
    dim_multiple_sats(metadata, dict, catalog, silver_schema, gold_schema)

    # Fact
    fact_tbl(metadata, dict, catalog, silver_schema, gold_schema)

    if project != "toolbox":
        pass
        # grant_permission(spark,metadata,env)
