# Databricks notebook source
from de_databricks.migrate.db_validate_migrate import validate_catalog_replication

# COMMAND ----------

# Usage:
PROJECT = dbutils.widgets.get("PROJECT").lower()
ENV = dbutils.widgets.get("ENV").lower()
validation_results = validate_catalog_replication(spark, f"{PROJECT}_{ENV}", f"{PROJECT}_{ENV}_v2")

# COMMAND ----------
