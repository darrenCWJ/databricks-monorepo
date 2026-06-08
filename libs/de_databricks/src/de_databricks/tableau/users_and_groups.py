from pyspark.sql.functions import *
from pyspark.sql.window import Window

from de_databricks.common.utils import *


def add_users_to_group(session, group_id, soe_list):
    soe = ",".join(soe_list)
    user_ids = {
        x["id"]: x["name"]
        for x in session.get(f"users?filter=name:in:[{soe}]&pageSize=1000")
        .json()["users"]
        .get("user", [])
    }

    for user_id in user_ids.keys():
        response = session.post(f"groups/{group_id}/users", json={"user": {"id": user_id}})
        message = f"User: {user_ids[user_id]} added"
        print_success_or_error(response, message)


def remove_users_from_group(session, group_id, soe_list):
    soe = ",".join(soe_list)
    user_ids = {
        x["id"]: x["name"]
        for x in session.get(f"users?filter=name:in:[{soe}]&pageSize=1000")
        .json()["users"]
        .get("user", [])
    }

    for user_id in user_ids.keys():
        response = session.delete(f"groups/{group_id}/users/{user_id}")
        message = f"User: {user_ids[user_id]} removed"
        print_success_or_error(response, message)


def sync_users_group(session, prefix, group_name, soe_list):

    # Validate group name prefix
    if not group_name.startswith(prefix):
        raise ValueError(
            f"[ERROR] Group Name: [{group_name}] does not start with Prefix: [{prefix}]"
        )

    group_id = session.get(f"groups?filter=name:eq:{group_name}").json()["groups"]["group"][0]["id"]
    users = [
        x["name"]
        for x in session.get(f"groups/{group_id}/users?pageSize=1000")
        .json()["users"]
        .get("user", [])
    ]

    # Add
    to_add = set(soe_list) - set(users)
    if len(to_add) > 0:
        add_users_to_group(session, group_id, to_add)

    # Remove
    to_remove = set(users) - set(soe_list)
    if len(to_remove) > 0:
        remove_users_from_group(session, group_id, to_remove)


def get_tableau_users_profile(spark, session):

    columns = ["email", "name", "siteRole", "lastLogin"]

    for page in range(1, 100):
        if page == 1:
            df = spark.createDataFrame(
                session.get(f"users?pageSize=1000&pageNumber={page}").json()["users"]["user"]
            ).select(*columns)
        else:
            users = session.get(f"users?pageSize=1000&pageNumber={page}").json()["users"]
            if users:
                tmp_df = spark.createDataFrame(users["user"]).select(*columns)
                df = df.union(tmp_df)
            else:
                break

    df = (
        df.withColumn("email", upper("email"))
        .withColumn("SOE", lower("name"))
        .withColumn(
            "Rank", row_number().over(Window.partitionBy("email").orderBy(desc("lastLogin")))
        )
        .filter(col("Rank") == 1)
        .drop("Rank")
        .select(
            col("email").alias("Email"),
            "SOE",
            col("name").alias("TableauSOE"),
            col("siteRole").alias("TableauSiteRole"),
        )
    )

    return df
