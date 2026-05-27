"""Gold layer — business aggregations for downstream dashboards and dbt."""

from __future__ import annotations

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def build_revenue_daily(spark: SparkSession, *, catalog: str) -> int:
    """Aggregate clean orders into daily revenue by region and product SKU.

    Full-refresh write — downstream consumers tolerate a brief unavailability.

    Returns:
        Number of rows written to gold.revenue_daily.
    """
    orders = spark.table(f"{catalog}.silver.orders_clean")

    revenue = (
        orders.withColumn("order_date", F.to_date("order_ts"))
        .withColumn("revenue", F.col("quantity") * F.col("unit_price"))
        .groupBy("order_date", "region", "product_sku")
        .agg(
            F.sum("revenue").alias("total_revenue"),
            F.count("order_id").alias("order_count"),
            F.sum("quantity").alias("total_units"),
            F.avg("unit_price").alias("avg_unit_price"),
        )
        .withColumn("_refreshed_at", F.current_timestamp())
    )

    (
        revenue.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .partitionBy("order_date")
        .saveAsTable(f"{catalog}.gold.revenue_daily")
    )

    row_count = revenue.count()
    print(f"[gold] revenue_daily: {row_count:,} rows written")
    return row_count
