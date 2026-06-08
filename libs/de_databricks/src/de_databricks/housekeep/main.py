# Databricks notebook source
import ast
import json
from datetime import datetime
from functools import reduce as _reduce

import requests
from dateutil.relativedelta import WE, relativedelta
from pyspark.sql.functions import *

from de_databricks.common.session import *
from de_databricks.housekeep.asset import *
from de_databricks.housekeep.notify import *
from de_databricks.housekeep.user import *

# COMMAND ----------

## initial config and environment check
## WARNING: DEBUG must always be False during development/testing
try:
    DEBUG = ast.literal_eval(dbutils.widgets.get("DEBUG"))
    ACCOUNT_NAME = dbutils.widgets.get("ACCOUNT")
except Exception:
    DEBUG = True
    ACCOUNT_NAME = "GovTech"

## parameter validation
if ACCOUNT_NAME not in ["GovTech", "GovTech Sandbox"]:
    raise Exception(
        "Invalid account parameter. It must be one of the following: GovTech, GovTech Sandbox"
    )

DEBUG

# COMMAND ----------


## temporary function for first-time implementation, not used anymore
def is_deletion_date():
    current_date = date.today()
    deactivation_date = current_date.replace(day=1) + relativedelta(day=1, weekday=WE(1))

    return current_date == deactivation_date


# COMMAND ----------

# load in config file and create ACCOUNT object
filePath = "./config.json"
with open(filePath) as f:
    config = json.load(f)

ACCOUNT = config["accounts"][ACCOUNT_NAME]

# COMMAND ----------

# Use the default secrets stored under the username scope
# Run the housekeeping pipeline either as an admin user
# or specify the client credentials in the parameters
ACCT_SESSION = create_databricks_acct_session(account_id=ACCOUNT["account_id"])

# select the corresponding workspace the notebook is run in
# todo: handle exceptions where workspace don't match config file
for workspace in ACCOUNT["workspaces"].values():
    if workspace["workspace_url"] == spark.conf.get("spark.databricks.workspaceUrl"):
        WORKSPACE = workspace
WORKSPACE_SESSION = create_databricks_workspace_session(workspace_url=WORKSPACE["workspace_url"])

# use this to run workspace-specific actions
# for name, workspace in ACCOUNT["workspaces"].items():
#    WORKSPACE = ACCOUNT["workspaces"][name]
#    WORKSPACE_SESSION = create_databricks_workspace_session(workspace_url=WORKSPACE["workspace_url"])

# COMMAND ----------

# Get the list of users from each workspace
active_users_df = get_active_users(WORKSPACE_SESSION, WORKSPACE["warehouse_id"])
all_users_df = get_account_users(ACCT_SESSION)
if ACCOUNT_NAME == "GovTech":
    all_wog_users_df = get_wog_users(WORKSPACE_SESSION, WORKSPACE["warehouse_id"], env="prd")
else:
    all_wog_users_df = active_users_df

# COMMAND ----------

# send reminder emails to users with upcoming inactive dates
if not DEBUG:
    remind_users(active_users_df, ACCOUNT_NAME, WORKSPACE["internal_url"])
elif DEBUG:
    debug_users_df = active_users_df.withColumn("email", lit("tan_wei_hao@tech.gov.sg"))
    remind_users(debug_users_df, ACCOUNT_NAME, WORKSPACE["internal_url"])

# COMMAND ----------

# execute deactivations on a weekly basis (reminders are no longer sent for expired accounts)
if not DEBUG:
    deactivate_users(
        all_wog_users_df,
        active_users_df,
        all_users_df,
        ACCOUNT_NAME,
        WORKSPACE["internal_url"],
        "deactivate",
        ACCT_SESSION,
    )
# elif not DEBUG and not is_deletion_date():
#    deactivate_users(all_wog_users_df,active_users_df, all_users_df, ACCOUNT_NAME, WORKSPACE["internal_url"])
elif DEBUG:
    test_users = active_users_df.withColumn("email", lit("null")).limit(1)
    debug_users_df = all_users_df.withColumn("email", lit("tan_wei_hao@tech.gov.sg")).limit(3)
    deactivate_users(
        all_wog_users_df, test_users, debug_users_df, ACCOUNT_NAME, WORKSPACE["internal_url"]
    )

# COMMAND ----------

# ## deactivation test
# test_email = "gabriel_lee_from.tp@tech.gov.sg"
# deactivate_user_by_email(test_email, account_session, account_id)
# test_user_id = get_user_id_by_email(test_email, account_session, account_id)
# databricks_host = account_session.url_base.replace("https://", "").split("/")[0]
# check_user_active_status(test_user_id, account_session, account_id, databricks_host) ## should show False

# ## reactivation test
# test_email = "gabriel_lee_from.tp@tech.gov.sg"
# reactivate_user_by_email(test_email, account_session, account_id)
# test_user_id = get_user_id_by_email(test_email, account_session, account_id)
# databricks_host = account_session.url_base.replace("https://", "").split("/")[0]
# check_user_active_status(test_user_id, account_session, account_id, databricks_host) ## should show True
