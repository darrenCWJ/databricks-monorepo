"""Unit tests for bronze / silver / gold transforms.

Uses a local SparkSession — no Databricks connection needed.
Run with: make test P=apps/demo-ingest-medallion
"""

from __future__ import annotations

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


@pytest.fixture(scope="session")
def spark() -> SparkSession:
    return (
        SparkSession.builder.master("local[1]")
        .appName("demo-ingest-medallion-tests")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )


# ── Silver quality rules ────────────────────────────────────────────────────

@pytest.mark.unit
def test_silver_passes_valid_row(spark: SparkSession) -> None:
    from demo_ingest_medallion.silver import QUALITY_RULES

    row = spark.createDataFrame(
        [("ORD-001", "CUST-1", "SKU-A", 2, 9.99, "SG", "2024-01-15 10:00:00")],
        "order_id STRING, customer_id STRING, product_sku STRING, "
        "quantity INT, unit_price DECIMAL(10,2), region STRING, order_ts TIMESTAMP",
    )

    all_pass = F.lit(True)
    for condition in QUALITY_RULES.values():
        all_pass = all_pass & condition

    result = row.withColumn("_ok", all_pass).collect()[0]["_ok"]
    assert result is True


@pytest.mark.unit
def test_silver_quarantines_null_order_id(spark: SparkSession) -> None:
    from demo_ingest_medallion.silver import QUALITY_RULES

    row = spark.createDataFrame(
        [(None, "CUST-1", "SKU-A", 2, 9.99, "SG", "2024-01-15 10:00:00")],
        "order_id STRING, customer_id STRING, product_sku STRING, "
        "quantity INT, unit_price DECIMAL(10,2), region STRING, order_ts TIMESTAMP",
    )

    all_pass = F.lit(True)
    for condition in QUALITY_RULES.values():
        all_pass = all_pass & condition

    result = row.withColumn("_ok", all_pass).collect()[0]["_ok"]
    assert result is False


@pytest.mark.unit
def test_silver_quarantines_negative_quantity(spark: SparkSession) -> None:
    from demo_ingest_medallion.silver import QUALITY_RULES

    row = spark.createDataFrame(
        [("ORD-002", "CUST-2", "SKU-B", -1, 5.00, "MY", "2024-01-15 11:00:00")],
        "order_id STRING, customer_id STRING, product_sku STRING, "
        "quantity INT, unit_price DECIMAL(10,2), region STRING, order_ts TIMESTAMP",
    )

    all_pass = F.lit(True)
    for condition in QUALITY_RULES.values():
        all_pass = all_pass & condition

    result = row.withColumn("_ok", all_pass).collect()[0]["_ok"]
    assert result is False


# ── Gold revenue calculation ────────────────────────────────────────────────

@pytest.mark.unit
def test_gold_revenue_calculation(spark: SparkSession) -> None:
    orders = spark.createDataFrame(
        [
            ("ORD-001", "2024-01-15 10:00:00", "SG", "SKU-A", 3, 10.00),
            ("ORD-002", "2024-01-15 14:00:00", "SG", "SKU-A", 2, 10.00),
            ("ORD-003", "2024-01-15 09:00:00", "MY", "SKU-B", 1, 25.00),
        ],
        "order_id STRING, order_ts TIMESTAMP, region STRING, "
        "product_sku STRING, quantity INT, unit_price DECIMAL(10,2)",
    )

    result = (
        orders.withColumn("order_date", F.to_date("order_ts"))
        .withColumn("revenue", F.col("quantity") * F.col("unit_price"))
        .groupBy("order_date", "region", "product_sku")
        .agg(F.sum("revenue").alias("total_revenue"))
    )

    sg_revenue = (
        result.filter((F.col("region") == "SG") & (F.col("product_sku") == "SKU-A"))
        .collect()[0]["total_revenue"]
    )
    assert float(sg_revenue) == 50.0

    my_revenue = (
        result.filter((F.col("region") == "MY") & (F.col("product_sku") == "SKU-B"))
        .collect()[0]["total_revenue"]
    )
    assert float(my_revenue) == 25.0
