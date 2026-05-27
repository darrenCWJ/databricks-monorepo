"""Bronze layer — raw ingestion from the landing zone."""

from __future__ import annotations

from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


ORDERS_SCHEMA = """
    order_id     STRING,
    customer_id  STRING,
    product_sku  STRING,
    quantity     INT,
    unit_price   DECIMAL(10,2),
    region       STRING,
    order_ts     TIMESTAMP
"""

CUSTOMERS_SCHEMA = """
    customer_id  STRING,
    full_name    STRING,
    email        STRING,
    country      STRING,
    created_at   TIMESTAMP
"""


def ingest_orders(spark: SparkSession, *, catalog: str) -> int:
    """Read raw orders from landing zone, append to bronze with ingestion metadata."""
    landing_path = f"dbfs:/{catalog}/landing/orders/"

    df = (
        spark.read.schema(ORDERS_SCHEMA)
        .option("header", "true")
        .option("mode", "PERMISSIVE")
        .csv(landing_path)
        .withColumn("_ingested_at", F.lit(datetime.now(timezone.utc).isoformat()))
        .withColumn("_source_path", F.input_file_name())
        .withColumn("_ingestion_date", F.current_date())
    )

    (
        df.write.format("delta")
        .mode("append")
        .partitionBy("_ingestion_date")
        .saveAsTable(f"{catalog}.bronze.orders")
    )

    count = df.count()
    print(f"[bronze] orders: {count:,} rows ingested from {landing_path}")
    return count


def ingest_customers(spark: SparkSession, *, catalog: str) -> int:
    """Read raw customer dimension from landing zone, full-refresh bronze."""
    landing_path = f"dbfs:/{catalog}/landing/customers/"

    df = (
        spark.read.schema(CUSTOMERS_SCHEMA)
        .option("header", "true")
        .csv(landing_path)
        .withColumn("_ingested_at", F.lit(datetime.now(timezone.utc).isoformat()))
        .withColumn("_source_path", F.input_file_name())
    )

    (
        df.write.format("delta")
        .mode("overwrite")
        .saveAsTable(f"{catalog}.bronze.customers")
    )

    count = df.count()
    print(f"[bronze] customers: {count:,} rows ingested from {landing_path}")
    return count
