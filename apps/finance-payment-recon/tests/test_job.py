import pytest
from pyspark.sql import SparkSession

from finance_payment_recon.reconcile import _apply_reconciliation, DISCREPANCY_THRESHOLD


@pytest.fixture(scope="session")
def spark() -> SparkSession:
    return SparkSession.builder.master("local[1]").appName("test").getOrCreate()


@pytest.mark.unit
def test_no_discrepancy_when_amounts_match(spark: SparkSession) -> None:
    df = spark.createDataFrame(
        [("p1", 100.00, 100.00, "2026-05-28")],
        ["payment_id", "amount", "bank_amount", "ingestion_date"],
    )
    result = _apply_reconciliation(df)
    row = result.collect()[0]
    assert row["is_discrepancy"] is False


@pytest.mark.unit
def test_discrepancy_flagged_when_variance_exceeds_threshold(spark: SparkSession) -> None:
    df = spark.createDataFrame(
        [("p2", 100.00, 100.05, "2026-05-28")],
        ["payment_id", "amount", "bank_amount", "ingestion_date"],
    )
    result = _apply_reconciliation(df)
    row = result.collect()[0]
    assert row["is_discrepancy"] is True


@pytest.mark.unit
def test_amount_within_threshold_not_flagged(spark: SparkSession) -> None:
    below = DISCREPANCY_THRESHOLD - 0.001
    df = spark.createDataFrame(
        [("p3", 100.00, 100.00 + below, "2026-05-28")],
        ["payment_id", "amount", "bank_amount", "ingestion_date"],
    )
    result = _apply_reconciliation(df)
    row = result.collect()[0]
    assert row["is_discrepancy"] is False


@pytest.mark.unit
def test_reconciliation_date_matches_ingestion_date(spark: SparkSession) -> None:
    df = spark.createDataFrame(
        [("p4", 50.00, 50.00, "2026-05-28")],
        ["payment_id", "amount", "bank_amount", "ingestion_date"],
    )
    result = _apply_reconciliation(df)
    row = result.collect()[0]
    assert row["reconciliation_date"] == "2026-05-28"
