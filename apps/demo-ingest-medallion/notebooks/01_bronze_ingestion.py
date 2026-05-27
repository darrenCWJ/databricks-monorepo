# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze — Raw Ingestion
# MAGIC
# MAGIC Reads raw order and customer files from the landing zone and writes
# MAGIC them to the bronze layer with ingestion metadata appended.
# MAGIC No transformations are applied — bronze is a faithful copy of the source.

# COMMAND ----------

dbutils.widgets.text("catalog", "cdo_dev")
catalog = dbutils.widgets.get("catalog")

# COMMAND ----------

from demo_ingest_medallion.bronze import ingest_orders, ingest_customers

ingest_orders(spark, catalog=catalog)
ingest_customers(spark, catalog=catalog)
