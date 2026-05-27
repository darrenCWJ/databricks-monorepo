# Databricks notebook source
# MAGIC %md
# MAGIC # Gold — Business Logic and Aggregation
# MAGIC
# MAGIC Reads from silver and produces `gold.revenue_daily` — daily revenue
# MAGIC totals broken down by region and product category.
# MAGIC Full-refresh write; downstream consumers tolerate a brief unavailability window.

# COMMAND ----------

dbutils.widgets.text("catalog", "cdo_dev")
catalog = dbutils.widgets.get("catalog")

# COMMAND ----------

from demo_ingest_medallion.gold import build_revenue_daily

rows_written = build_revenue_daily(spark, catalog=catalog)
print(f"gold.revenue_daily refreshed — {rows_written:,} rows written")
