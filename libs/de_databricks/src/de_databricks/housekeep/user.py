from datetime import datetime

import requests
from dateutil.relativedelta import WE, relativedelta
from pyspark.sql.functions import *

from de_databricks.housekeep.notify import *


## user management
def get_user_id_by_email(email, acct_session):
    try:
        # current default number of users returned is 10,000
        response = acct_session.get("scim/v2/Users")
        data = response.json()
    except Exception as e:
        print(f"SCIM API query failed: {e}")
        return None
    for user in data.get("Resources", []):
        if user.get("userName", "").lower() == email.lower():
            return user["id"]
    return None


def deactivate_user_by_email(email, acct_session):
    user_id = get_user_id_by_email(email, acct_session)
    if not user_id:
        print(f"Unable to find user: {email}")
        return
    payload = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [{"op": "replace", "path": "active", "value": False}],
    }
    response = acct_session.patch(
        f"scim/v2/Users/{user_id}",
        json=payload,
        headers={"Content-Type": "application/scim+json"},
    )
    if response.status_code == 200:
        print(f"Deactivated: {email}")
    else:
        print(f"Failed deactivation: {email} - Response code {response.status_code}")


def reactivate_user_by_email(email, acct_session):
    user_id = get_user_id_by_email(email, acct_session)
    if not user_id:
        print(f"Unable to find user: {email}")
        return
    payload = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [{"op": "replace", "path": "active", "value": True}],
    }
    response = acct_session.patch(
        f"scim/v2/Users/{user_id}",
        json=payload,
        headers={"Content-Type": "application/scim+json"},
    )
    if response.status_code == 200:
        print(f"Reactivated: {email}")
    else:
        print(f"Failed reactivation: {email} - Response code {response.status_code}")


def get_workspace_users(workspace_session):
    response = workspace_session.get("preview/scim/v2/Users")
    response = response.json()
    df = [{"email": x["userName"].lower(), "id": x["id"]} for x in response["Resources"]]
    return spark.createDataFrame(df)


def get_account_users(acct_session):
    response = acct_session.get("scim/v2/Users")
    response = response.json()
    df = [{"email": x["userName"].lower(), "id": x["id"]} for x in response["Resources"]]
    return spark.createDataFrame(df)


def get_active_users(workspace_session, warehouse_id):
    payload = {
        "on_wait_timeout": "CANCEL",
        "statement": "WITH active_users as ( \
            SELECT lower(user_identity.email) AS email, action_name, event_time FROM system.access.audit \
            WHERE service_name = 'accounts' \
            AND (action_name = 'workspaceLoginCodeAuthentication' \
                OR action_name = 'samlLogin') \
            AND event_time >= date_sub(current_date(), 90) \
            AND user_identity.email LIKE '%@%' \
            UNION ALL \
            SELECT lower(request_params.targetUserName) AS email, action_name, event_time FROM system.access.audit \
            WHERE service_name = 'accounts' \
            AND action_name = 'add' \
            AND event_time >= date_sub(current_date(), 90) \
            AND request_params.targetUserName LIKE '%@%' \
            ) \
            SELECT email, max(action_name) AS action_name, max(event_time) AS last_action  \
            FROM active_users \
            GROUP BY email",
        "wait_timeout": "50s",
        "warehouse_id": warehouse_id,
    }
    response = workspace_session.post(
        "sql/statements/",
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    response = response.json()

    schema = ""
    for column in response["manifest"]["schema"]["columns"]:
        schema += f"{column['name']} {column['type_text']}, "
    schema = schema[:-2]

    for i in range(len(response["result"]["data_array"])):
        response["result"]["data_array"][i][2] = datetime.fromisoformat(
            response["result"]["data_array"][i][2]
        )
    user_df = spark.createDataFrame(response["result"]["data_array"], schema=schema)
    return user_df


def get_wog_users(workspace_session, warehouse_id, env):
    payload = {
        "on_wait_timeout": "CANCEL",
        "statement": f"SELECT lower(Email) as email from mst_{env}.mart.mst_wog_ad_user_account",
        "wait_timeout": "50s",
        "warehouse_id": warehouse_id,
    }
    response = workspace_session.post(
        "sql/statements/",
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    response = response.json()

    schema = ""
    for column in response["manifest"]["schema"]["columns"]:
        schema += f"{column['name']} {column['type_text']}, "
    schema = schema[:-2]

    user_df = spark.createDataFrame(response["result"]["data_array"], schema=schema)
    return user_df


def remind_users(active_users_df, env, url):
    remind_users_df = active_users_df.select(
        "*", timestamp_add("DAY", lit(91), active_users_df.last_action).alias("inactive_date")
    )
    remind_users_df = remind_users_df.withColumn(
        "days_left", datediff(remind_users_df.inactive_date, current_timestamp())
    )

    email_users_df = remind_users_df.filter(remind_users_df.days_left <= 30)
    to_emails = email_users_df.drop("last_action", "days_left").collect()
    for row in to_emails:
        remind_inactive_users(env, url, [row["email"]], row["inactive_date"])

    admin_emails = [
        "tan_wei_hao@tech.gov.sg",
        "jeffrey_siew@tech.gov.sg",
        "germaine_tan@tech.gov.sg",
    ]
    email_admin_report(env, email_users_df.collect(), admin_emails, "Inactive Account")


def deactivate_users(
    all_wog_users_df,
    active_users_df,
    all_users_df,
    env,
    url,
    operation="notify",
    account_session=None,
):
    total_active_users_df = active_users_df.join(all_wog_users_df, "email", "inner")
    inactive_users_df = all_users_df.join(total_active_users_df, "email", "left_anti")

    if operation == "deactivate":
        for record in inactive_users_df.collect():
            deactivate_user_by_email(record["email"], account_session)
    elif operation == "notify":
        to_emails = [row["email"] for row in inactive_users_df.collect()]
        notify_inactive_users(env, url, to_emails)

        admin_emails = [
            "tan_wei_hao@tech.gov.sg",
            "jeffrey_siew@tech.gov.sg",
            "germaine_tan@tech.gov.sg",
        ]
        email_admin_report(env, inactive_users_df.collect(), admin_emails, "Expired Account")

    return inactive_users_df


def check_user_active_status(user_id, acct_session):
    response = acct_session.get(f"scim/v2/Users/{user_id}")
    if response.status_code == 200:
        status = response.json().get("active")
        print(f" User active status: {status}")
        return status
    else:
        print(f"Failed to fetch user: {response.status_code}\n{response.text}")
        return None
