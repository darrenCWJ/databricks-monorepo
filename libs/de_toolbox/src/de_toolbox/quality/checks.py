import os
import sys

from de_toolbox.catalog import get_catalog, get_repo_path

path = "/Workspace/Repos/shared/de_databricks"
if path not in sys.path:
    sys.path.append(os.path.abspath(path))
import ast

from account.iam import *
from common.session import *
from pyspark.sql.functions import *


def dq_checks(_spark, metadata, project, env):
    global spark
    spark = _spark

    # Create Catalog and schema if not exists
    catalog_dq = f"databricks_dq_{env}"

    spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog_dq}")
    spark.sql(f"USE CATALOG {catalog_dq}")

    session = create_databricks_session()
    org_id = spark.conf.get("spark.databricks.clusterUsageTags.clusterOwnerOrgId")
    is_prd = org_id.endswith("5212")

    if is_prd:
        principal = create_or_get_service_principal(session, "prd_admin_principal")
        prd_p_id = principal["applicationId"]
        spark.sql(
            f"GRANT USE_CATALOG, USE_SCHEMA, CREATE_SCHEMA, CREATE_TABLE ON CATALOG {catalog_dq} TO `{prd_p_id}`"
        )
    else:
        principal = create_or_get_service_principal(session, "uat_admin_principal")
        uat_p_id = principal["applicationId"]
        spark.sql(
            f"GRANT USE_CATALOG, USE_SCHEMA, CREATE_SCHEMA, CREATE_TABLE ON CATALOG {catalog_dq} TO `{uat_p_id}`"
        )

    spark.sql(f"CREATE SCHEMA if not exists {catalog_dq}.{project}")

    if project == "toolbox":
        spark.sql(f"ALTER CATALOG {catalog_dq} OWNER TO `{env}_dart_owners`")
        spark.sql(f"ALTER SCHEMA {project} OWNER TO `{env}_dart_owners`")
        read_catalog = f"test_{env}"
    else:
        spark.sql(f"ALTER CATALOG {catalog_dq} OWNER TO `{env}_dart_owners`")
        spark.sql(f"ALTER SCHEMA {project} OWNER TO `{env}_dart_owners`")
        read_catalog = get_catalog(project, env)

    if is_prd:
        spark.sql(f"GRANT USE_CATALOG, USE_SCHEMA ON CATALOG {catalog_dq} TO `{env}_dart_dm`")
        spark.sql(f"GRANT SELECT ON SCHEMA {catalog_dq}.{project} TO `{env}_dart_dm`")
    else:
        spark.sql(f"GRANT USE_CATALOG, USE_SCHEMA ON CATALOG {catalog_dq} TO `{env}_dart_dm`")
        spark.sql(f"GRANT SELECT ON SCHEMA {catalog_dq}.{project} TO `{env}_dart_dm`")

    base_path = get_repo_path(project, debug=None, folder="data_quality")
    metadata_path = f"{base_path}/{metadata}.json"

    env_dic = {"ENV": f"{env}", "PROJECT": f"{project}"}

    metadata = open(metadata_path).read()
    for k, v in env_dic.items():
        metadata = metadata.replace("{{ " + k + " }}", v)

    metadata = ast.literal_eval(metadata)

    table_name = metadata["table_name"]
    pk = metadata["primary_key"]
    schema = metadata["schema"]
    source = metadata["source"]
    domain = metadata["domain"]
    subdomain = metadata["subdomain"]

    df = spark.read.table(f"{read_catalog}.{schema}.{table_name}")

    if schema == "gold":
        for cols in df.columns:
            if cols in ["EffectiveFrom", "EffectiveTo"]:
                dts = "EffectiveFrom"
            else:
                dts = "null"
    else:
        dts = "_LOAD_DTS"

    for column_completeness in metadata["completeness"]:
        df = df.withColumn(
            f"{column_completeness}_Completeness",
            expr(
                f"case when {column_completeness} is null or {column_completeness} == '0' then 'False' else 'True' end"
            ),
        )

    for column_conformity, rules in metadata["confirmity"].items():
        df = df.withColumn(
            f"{column_conformity}_Conformity",
            expr(
                f"case when {column_conformity} is null then 'Invalid' when {rules} then 'True' else 'False' end"
            ),
        )

    for column_validity, rules in metadata["validity"].items():
        df = df.withColumn(
            f"{column_validity}_Validity",
            expr(
                f"case when {column_conformity} is null then 'Invalid' when {rules} then 'True' else 'False' end"
            ),
        )

    for column_uniqueness in metadata["uniqueness"]:
        df = df.withColumn(
            f"{column_uniqueness}_Uniqueness_cnt",
            expr(
                f"count(*) over (partition by {column_uniqueness}, {dts} order by {column_uniqueness}, {dts})"
            ),
        )
        df = df.withColumn(
            f"{column_uniqueness}_Uniqueness",
            expr(f"case when {column_uniqueness}_Uniqueness_cnt = 1 then 'True' else 'False' end"),
        ).drop(f"{column_uniqueness}_Uniqueness_cnt")

    # LEVEL 3 WRITE TO TEMP VIEW
    df = (
        df.withColumn("Source", lit(f"{source}"))
        .withColumn("Domain", lit(f"{domain}"))
        .withColumn("Subdomain", lit(f"{subdomain}"))
    )

    df.createOrReplaceTempView(f"{table_name}_source")

    dimension_cols = []
    dimension_stack = []

    for column in df.columns:
        for dimension in ["_Completeness", "_Conformity", "_Validity", "Uniqueness"]:
            if dimension in column:
                dimension_cols.append(column)
                dimension_stack.append("'" + column + "'," + column)

    dimension_str = ", ".join(dimension_cols)
    dimension_stack = ", ".join(dimension_stack)
    cnt = len(dimension_cols)

    if not schema == "gold":
        base = f"""select * except(Dimension), right(Dimension, charindex('_', reverse(Dimension)) - 1) as Dimension, left(Dimension, charindex('_', Dimension) - 1) as ColumnName  
                    from (select * except({dimension_str}), STACK({cnt}, {dimension_stack}) as (Dimension,Flg), dense_rank() over(order by {dts} desc) as rnk from {table_name}_source)
                    where rnk = 1
                """
    else:
        base = f"""select * except(Dimension), right(Dimension, charindex('_', reverse(Dimension)) - 1) as Dimension, left(Dimension, charindex('_', Dimension) - 1) as ColumnName  
                    from (select * except({dimension_str}), STACK({cnt}, {dimension_stack}) as (Dimension,Flg) from {table_name}_source)
                """

    df_v2 = spark.sql(f"""
                select {pk}, Source, Domain, Subdomain, columnname as DataElement, Dimension, Flg as Flag, {dts}, current_date() as last_refreshed from ({base})
            """)

    df_v1 = spark.sql(f"""
                select distinct(*) from (
                    select Source, Domain, Subdomain, columnname as DataElements, Dimension, {dts}, Percentage, current_date() as last_refreshed from (
                        select dimension, Source, Domain, Subdomain, {dts}, columnname, round(count(case when flg = True then 1 end)/count(*)*100,2) as Percentage
                        from ({base})
                        group by 1,2,3,4,5,6
                    )
                )
            """)

    for cols in df_v2.columns:
        if cols == "NULL":
            df_v2 = df_v2.drop("NULL")

    # df_v1.write.option("mergeSchema", "true").mode("overwrite").saveAsTable(f'{catalog_dq}.{project}.{table_name}_lvl1')
    df_v2.write.option("mergeSchema", "true").mode("append").saveAsTable(
        f"{catalog_dq}.{project}.{table_name}_lvl2"
    )
