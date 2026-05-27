# Databricks notebook source
# MAGIC %md
# MAGIC # Silver — Cleaning and Validation
# MAGIC
# MAGIC Reads from bronze, applies schema enforcement, deduplication, and
# MAGIC data-quality checks. Quarantines bad rows rather than dropping them.
# MAGIC Output is a clean, validated order dataset ready for gold aggregation.

# COMMAND ----------

dbutils.widgets.text("catalog", "cdo_dev")
catalog = dbutils.widgets.get("catalog")

# COMMAND ----------

from demo_ingest_medallion.silver import process_orders

quarantine_count = process_orders(spark, catalog=catalog)

if quarantine_count > 0:
    print(f"[WARN] {quarantine_count} rows quarantined — check {catalog}.silver.orders_quarantine")
