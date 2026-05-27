"""Silver layer — schema enforcement, deduplication, and data-quality checks."""

from __future__ import annotations

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T


QUALITY_RULES = {
    "order_id_not_null": F.col("order_id").isNotNull(),
    "customer_id_not_null": F.col("customer_id").isNotNull(),
    "quantity_positive": F.col("quantity") > 0,
    "unit_price_positive": F.col("unit_price") > 0,
    "order_ts_not_null": F.col("order_ts").isNotNull(),
}


def process_orders(spark: SparkSession, *, catalog: str) -> int:
    """Clean and validate bronze orders; quarantine failures; write to silver.

    Returns:
        Number of rows sent to quarantine.
    """
    bronze = spark.table(f"{catalog}.bronze.orders")

    # Build a single pass-or-fail column per row
    all_pass = F.lit(True)
    fail_reasons = F.array()

    for rule_name, condition in QUALITY_RULES.items():
        all_pass = all_pass & condition
        fail_reasons = F.when(
            ~condition,
            F.array_append(fail_reasons, F.lit(rule_name)),
        ).otherwise(fail_reasons)

    annotated = bronze.withColumn("_dq_passed", all_pass).withColumn(
        "_dq_failures", fail_reasons
    )

    clean = annotated.filter(F.col("_dq_passed"))
    quarantine = annotated.filter(~F.col("_dq_passed"))

    # Deduplicate on order_id — keep the latest ingestion
    clean_deduped = (
        clean.withColumn(
            "_row_num",
            F.row_number().over(
                F.Window.partitionBy("order_id").orderBy(
                    F.col("_ingested_at").desc()
                )
            ),
        )
        .filter(F.col("_row_num") == 1)
        .drop("_row_num", "_dq_passed", "_dq_failures")
    )

    (
        clean_deduped.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(f"{catalog}.silver.orders_clean")
    )

    quarantine_count = quarantine.count()
    if quarantine_count > 0:
        (
            quarantine.write.format("delta")
            .mode("append")
            .saveAsTable(f"{catalog}.silver.orders_quarantine")
        )

    clean_count = clean_deduped.count()
    print(f"[silver] orders_clean: {clean_count:,} rows written")
    print(f"[silver] orders_quarantine: {quarantine_count:,} rows quarantined")
    return quarantine_count
