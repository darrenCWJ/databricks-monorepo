"""Ingest raw payment records from the external payments API into bronze."""

from __future__ import annotations

import datetime as dt
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F


def ingest_payments(catalog: str, run_date: dt.date | None = None) -> DataFrame:
    """Fetch payments from the API and land them in bronze.

    Reads : external payments API (REST)
    Writes: {catalog}.bronze.raw_payments  (append, partitioned by ingestion_date)
    """
    spark = SparkSession.getActiveSession()
    assert spark is not None, "No active Spark session"

    effective_date = run_date or dt.date.today()

    # TODO: replace with real API client call
    raw_df = _fetch_from_api(spark, effective_date)

    output = raw_df.withColumn("ingestion_date", F.lit(str(effective_date)))
    (
        output.write
        .format("delta")
        .mode("append")
        .partitionBy("ingestion_date")
        .saveAsTable(f"{catalog}.bronze.raw_payments")
    )
    return output


def _fetch_from_api(spark: SparkSession, run_date: dt.date) -> DataFrame:
    """Stub — replace with actual API client logic."""
    raise NotImplementedError("API client not yet implemented")
