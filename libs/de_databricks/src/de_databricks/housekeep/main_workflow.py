# Databricks notebook source
from de_databricks.common.session import *
from de_databricks.workflow.job import *

session = create_databricks_session()

BRANCH = "f_housekeeping"
ENV = "sandbox"
DEBUG = True

create_or_update_job(
    session,
    config="housekeeping.json",
    debug=DEBUG,
    CLUSTER_ID="0917-053118-rwf23xci-v2n",
    ENV=ENV,
    GIT_BRANCH=BRANCH,
    GIT_URL="https://sgts.gitlab-dedicated.com/wog/gvt/dart/gvt-dsaid-dart/cdo/data-engineer/de_databricks.git",
    PROJECT="admin",
)

# COMMAND ----------
