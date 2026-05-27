"""Reconcile bronze payment records and write discrepancy flags to gold."""

from __future__ import annotations

import datetime as dt
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F


DISCREPANCY_THRESHOLD = 0.01


def reconcile_payments(catalog: str, run_date: dt.date | None = None) -> DataFrame:
    """Compare payment records against bank statements and flag discrepancies.

    Reads : {catalog}.bronze.raw_payments
    Writes: {catalog}.gold.payment_recon  (overwrite for run_date partition)
    """
    spark = SparkSession.getActiveSession()
    assert spark is not None, "No active Spark session"

    effective_date = run_date or dt.date.today()

    payments = spark.table(f"{catalog}.bronze.raw_payments").filter(
        F.col("ingestion_date") == str(effective_date)
    )

    reconciled = _apply_reconciliation(payments)

    (
        reconciled.write
        .format("delta")
        .mode("overwrite")
        .option("replaceWhere", f"reconciliation_date = '{effective_date}'")
        .saveAsTable(f"{catalog}.gold.payment_recon")
    )
    return reconciled


def _apply_reconciliation(payments: DataFrame) -> DataFrame:
    """Flag records where amount variance exceeds threshold."""
    return payments.withColumn(
        "is_discrepancy",
        F.abs(F.col("amount") - F.col("bank_amount")) > F.lit(DISCREPANCY_THRESHOLD),
    ).withColumn(
        "reconciliation_date", F.col("ingestion_date")
    )
