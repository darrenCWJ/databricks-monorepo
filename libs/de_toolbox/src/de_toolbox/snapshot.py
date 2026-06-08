"""Monthly snapshot creation for gold-layer reporting.

Creates point-in-time snapshots at month-end boundaries with fiscal year alignment.
"""

from datetime import datetime

from dateutil.relativedelta import relativedelta
from pyspark.sql import DataFrame, SparkSession


def get_month_end_dates(start_date, end_date) -> list:
    """Generate list of month-end dates between start_date and end_date (inclusive).

    Args:
        start_date: Start date (date object or "YYYY-MM-DD" string).
        end_date: End date (date object or "YYYY-MM-DD" string).

    Returns:
        List of date objects representing each month's last day.
    """
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    current_date = start_date.replace(day=1) + relativedelta(months=1, days=-1)
    month_end_dates = []

    while current_date <= end_date.replace(day=1) + relativedelta(months=1, days=-1):
        month_end_dates.append(current_date)
        current_date = (current_date + relativedelta(days=1)).replace(day=1) + relativedelta(
            months=1, days=-1
        )

    return month_end_dates


def create_monthly_snapshot(
    spark: SparkSession,
    df: DataFrame,
    primary_keys: list[str] | str | None = None,
    order_by_column: str = "_INGEST_DATE",
    snapshot_type: str = "period",
    report_date_adjustment: int = 0,
) -> DataFrame:
    """Create snapshot data by period (month-end) or current (latest only).

    Adds reporting columns: _REPORT_DATE, _REPORT_DATE_YEAR, _REPORT_DATE_MONTH,
    _REPORT_DATE_QUARTER (fiscal year starting April).

    Args:
        spark: Active SparkSession.
        df: Input DataFrame with a date/timestamp column.
        primary_keys: Column(s) for deduplication. Required for snapshot_type="period".
        order_by_column: Date/timestamp column to order by (default "_INGEST_DATE").
        snapshot_type: "period" for month-end snapshots, "current" for latest data only.
        report_date_adjustment: Days to offset report date (e.g., -1 for overnight ingestion).

    Returns:
        DataFrame with snapshot data and report date columns.

    Raises:
        ValueError: If primary_keys missing for period snapshot.
    """
    if isinstance(primary_keys, str):
        pk_cols = [primary_keys]
    elif primary_keys is None:
        pk_cols = []
    else:
        pk_cols = primary_keys if primary_keys else []

    if snapshot_type != "current" and not pk_cols:
        raise ValueError(
            "Primary keys are required for snapshot_type='period'. "
            "For full data dumps without primary keys, use snapshot_type='current'."
        )

    df.createOrReplaceTempView("input_data")

    partition_cols = ", ".join(pk_cols) if pk_cols else ""

    transformed_df = spark.sql(f"""
    SELECT *,
        DATE(DATEADD(day, {report_date_adjustment}, {order_by_column})) as _REPORT_DATE,
        CASE
            WHEN MONTH(DATE(DATEADD(day, {report_date_adjustment}, {order_by_column}))) >= 4
            THEN YEAR(DATE(DATEADD(day, {report_date_adjustment}, {order_by_column})))
            ELSE YEAR(DATE(DATEADD(day, {report_date_adjustment}, {order_by_column}))) - 1
        END as _REPORT_DATE_YEAR,
        MONTH(DATE(DATEADD(day, {report_date_adjustment}, {order_by_column}))) as _REPORT_DATE_MONTH,
        CONCAT(
            CASE
                WHEN MONTH(DATE(DATEADD(day, {report_date_adjustment}, {order_by_column}))) >= 4
                THEN YEAR(DATE(DATEADD(day, {report_date_adjustment}, {order_by_column})))
                ELSE YEAR(DATE(DATEADD(day, {report_date_adjustment}, {order_by_column}))) - 1
            END,
            'Q',
            CASE
                WHEN MONTH(DATE(DATEADD(day, {report_date_adjustment}, {order_by_column}))) BETWEEN 4 AND 6 THEN 1
                WHEN MONTH(DATE(DATEADD(day, {report_date_adjustment}, {order_by_column}))) BETWEEN 7 AND 9 THEN 2
                WHEN MONTH(DATE(DATEADD(day, {report_date_adjustment}, {order_by_column}))) BETWEEN 10 AND 12 THEN 3
                WHEN MONTH(DATE(DATEADD(day, {report_date_adjustment}, {order_by_column}))) BETWEEN 1 AND 3 THEN 4
            END
        ) as _REPORT_DATE_QUARTER
    FROM input_data
    """)

    transformed_df.createOrReplaceTempView("transformed_data")

    if snapshot_type == "current":
        max_date_result = spark.sql(f"""
        SELECT MAX({order_by_column}) as max_date FROM transformed_data
        """).collect()[0]
        max_date = max_date_result["max_date"]

        final_df = spark.sql(f"""
        SELECT * FROM transformed_data WHERE {order_by_column} = '{max_date}'
        """)
    else:
        date_range = spark.sql("""
        SELECT
            MIN(_REPORT_DATE) as min_date,
            MAX(_REPORT_DATE) as max_date,
            LAST_DAY(MAX(_REPORT_DATE)) as last_day_of_max_month
        FROM transformed_data
        """).collect()[0]

        min_date = date_range["min_date"]
        max_date = date_range["max_date"]
        last_day_of_max_month = date_range["last_day_of_max_month"]

        month_end_dates = get_month_end_dates(min_date, max_date)
        month_end_dates_df = spark.createDataFrame(
            [(date,) for date in month_end_dates], ["month_end_date"]
        )
        month_end_dates_df.createOrReplaceTempView("month_end_dates")

        historical_data = spark.sql(f"""
        WITH ranked_data AS (
            SELECT t.*,
                ROW_NUMBER() OVER (
                    PARTITION BY {partition_cols}, _REPORT_DATE
                    ORDER BY {order_by_column} DESC
                ) as rn
            FROM transformed_data t
            INNER JOIN month_end_dates m ON t._REPORT_DATE = m.month_end_date
        )
        SELECT * EXCEPT(rn) FROM ranked_data WHERE rn = 1
        """)

        is_max_date_month_end = max_date == last_day_of_max_month

        if not is_max_date_month_end:
            latest_data = spark.sql(f"""
            WITH ranked_latest AS (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY {partition_cols if partition_cols else "1"}, _REPORT_DATE
                        ORDER BY {order_by_column} DESC
                    ) as rn
                FROM transformed_data
                WHERE _REPORT_DATE = '{max_date}'
            )
            SELECT * EXCEPT(rn) FROM ranked_latest WHERE rn = 1
            """)
            final_df = historical_data.union(latest_data)
        else:
            final_df = historical_data

    all_columns = final_df.columns
    regular_columns = sorted([col for col in all_columns if not col.startswith("_")])
    underscore_columns = sorted([col for col in all_columns if col.startswith("_")])
    ordered_columns = regular_columns + underscore_columns

    if snapshot_type == "current":
        order_by_cols = [order_by_column]
    else:
        order_by_cols = pk_cols + [order_by_column]

    return final_df.select(*ordered_columns).orderBy(*order_by_cols)
