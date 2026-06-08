# Databricks notebook source
from de_toolbox.catalog import get_catalog
from pyspark.sql.functions import *

from de_databricks.common.session import *
from de_databricks.tableau.users_and_groups import *

# COMMAND ----------


def main():

    catalog = get_catalog(dbutils.widgets.get("PROJECT"), dbutils.widgets.get("ENV"))
    prefix = dbutils.widgets.get("PREFIX")
    table = dbutils.widgets.get("ENTITLEMENT_TABLE")

    # DataBricks Session
    db_session = create_databricks_session()
    # Tableau Session
    session = create_tableau_session(db_session)

    # Get dictionary of letter-case matching SOE
    userprofile = get_tableau_users_profile(spark, session)
    userprofile = {row["SOE"]: row["TableauSOE"] for row in userprofile.collect()}

    df = (
        spark.read.table(f"{catalog}.entitlement.{table}")
        .withColumn(
            "TableauUserGroup",
            explode(
                udf(
                    lambda x: [y.strip() for y in x.split(";")], returnType=ArrayType(StringType())
                )("TableauUserGroup")
            ),
        )
        .groupby("TableauUserGroup")
        .agg(collect_set("UserName").alias("UserName"))
        .withColumn(
            "UserName",
            udf(lambda x: [userprofile.get(y.lower(), y) for y in x], ArrayType(StringType()))(
                "UserName"
            ),
        )
    )

    for row in df.collect():
        # Param Prefix - Validate Tableau Group Name
        sync_users_group(session, prefix, row[0], row[1])


# COMMAND ----------

main()
