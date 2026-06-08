from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql.window import Window


def _get_pit_df(spark, catalog, satellites, primary_keys, report_type=None):
    s1 = []
    s2 = []
    s3 = []
    hash_primary_key = "Hash" + "".join(primary_keys)

    # Modify the date adjustment clause based on report_type
    date_adjust = (
        "(_LOAD_DTS - INTERVAL 1 DAY) as adjusted_date"
        if report_type == "daily_business_report"
        else "_LOAD_DTS as adjusted_date"
    )

    for table in satellites:
        s1.append(f"""
            SELECT 
                {hash_primary_key}, 
                {date_adjust}
            FROM {catalog}.silver.{table}
        """)
        s2.append(
            f"MAX({table}.adjusted_date) OVER (PARTITION BY LD.{hash_primary_key} ORDER BY LD.adjusted_date) AS {table}_LOAD_DTS"
        )
        s3.append(
            f"""LEFT JOIN (
                SELECT {hash_primary_key}, {date_adjust}
                FROM {catalog}.silver.{table}
            ) {table} 
            ON {table}.{hash_primary_key} = LD.{hash_primary_key} 
            AND {table}.adjusted_date = LD.adjusted_date"""
        )

    s1 = " UNION ".join(s1)
    s2 = ",".join(s2)
    s3 = " ".join(s3)

    query = f"""
    WITH df AS (
      WITH LOAD_DATES AS (
        {s1}
      )
      SELECT
       LD.{hash_primary_key},
       LD.adjusted_date AS EffectiveFrom,
       LEAD(LD.adjusted_date) OVER (PARTITION BY LD.{hash_primary_key} ORDER BY LD.adjusted_date) EffectiveTo,
       {s2}
      FROM LOAD_DATES LD
      {s3}
      ORDER BY {hash_primary_key}
    )
    SELECT * FROM df
    """
    return spark.sql(query)


# Get Dimension Table (Hub + Satellite) SCD Type 1/2
def get_dim_table(
    spark,
    catalog,
    hub,
    satellites,
    primary_keys,
    scd_type,
    join_type="left",
    report_type=None,
    prefix_satellite_columns=False,
):
    """
    Creates a dimension table by joining hub/link and satellite tables using SCD Type 1 or 2 patterns.
    This function combines business keys from hub/link with attributes from satellites while
    maintaining historical changes based on the specified SCD type.

    Pattern 1 - Hub and Satellites:
    Input Hub Table:
    HashCustomerID  CustomerID  _LOAD_DTS
    def456          C1          2023-01-01
    mno345          C2          2023-01-01

    Input Satellite Tables:
    sat_customer_details:
    HashCustomerID  Name    Address     _LOAD_DTS
    def456          John    123 St      2023-01-01
    def456          John    456 Ave     2023-02-01
    mno345          Jane    789 Rd      2023-01-01

    Output with SCD Type 1:
    CustomerID  Name  Address  _LOAD_DTS
    C1          John  456 Ave  2023-02-01
    C2          Jane  789 Rd   2023-01-01

    Output with SCD Type 2:
    CustomerID  Name  Address  EffectiveFrom  EffectiveTo
    C1          John  123 St   2023-01-01     2023-02-01
    C1          John  456 Ave  2023-02-01     9999-12-31
    C2          Jane  789 Rd   2023-01-01     9999-12-31

    Pattern 2 - Link and Satellites:
    Input Link Table:
    HashEmployeeIdOrganizationId  HashEmployeeId  HashOrganizationId  EmployeeId  OrganizationId  _LOAD_DTS
    abc123                        emp456          org789              E1          O1              2023-01-01
    def456                        emp789          org101              E2          O2              2023-01-01

    Input Satellite Tables:
    sat_employee_organization:
    HashEmployeeIdOrganizationId  Role         Department  _LOAD_DTS
    abc123                        Manager      Sales       2023-01-01
    abc123                        Director     Sales       2023-02-01
    def456                        Analyst      IT          2023-01-01

    Output with SCD Type 1:
    EmployeeId  OrganizationId  Role      Department  _LOAD_DTS
    E1         O1               Director   Sales      2023-02-01
    E2         O2               Analyst    IT         2023-01-01

    Output with SCD Type 2:
    EmployeeId  OrganizationId  Role      Department  EffectiveFrom  EffectiveTo
    E1         O1               Manager   Sales       2023-01-01     2023-02-01
    E1         O1               Director  Sales       2023-02-01     9999-12-31
    E2         O2               Analyst   IT          2023-01-01     9999-12-31

    Pattern 3 - Link Self-Join:
    Input Link Table (lnk_employee_organization):
    HashEmployeeIdOrganizationId  HashEmployeeId  HashOrganizationId  EmployeeId  OrganizationId  _LOAD_DTS
    abc123                        emp456          org789              E1          O1              2023-01-01
    def456                        emp456          org101              E1          O2              2023-02-01
    ghi789                        emp456          org202              E1          O3              2023-03-01
    jkl101                        emp789          org789              E2          O1              2023-01-01
    mno202                        emp456          org101              E1          O4              2023-04-01

    Args:
        spark: SparkSession object for database operations
        catalog: Database catalog name containing the tables
        hub: Name of the hub or link table
        satellites: List of satellite table names or same link table with alias
        primary_keys: List of business key column names from the hub/link table
        scd_type: Type of Slowly Changing Dimension pattern:
            1: Only latest records (Type 1)
            2: Historical records with effective dates (Type 2)
        join_type: Type of join to perform ("left", "right", "inner", "outer", default: "left")
        report_type: Expect "daily_business_report" or None, this is used to globally apply a logic to reduce date by 1 from _LOAD_DTS and all derivative columns from _LOAD_DTS
        prefix_satellite_columns: Boolean to enable/disable prefixing satellite names to column names (default: False)
                                When True, adds satellite name as prefix to prevent column name conflicts
                                Example: "BusinessTitle" becomes "sat_employee_details_BusinessTitle"

    Returns:
        DataFrame containing:
        For SCD Type 1:
        - Business keys from hub/link table
        - Latest valid attributes
        For SCD Type 2:
        - Business keys from hub/link table
        - Historical attributes
        - EffectiveFrom: Start date of attribute validity
        - EffectiveTo: End date of attribute validity
    """
    # Add validation for link tables
    if hub.startswith("lnk"):
        # Check if any satellite is a link table
        link_satellites = [sat for sat in satellites if sat.startswith("lnk")]

        if link_satellites:
            # If there are link tables in satellites, they must be self-joins
            if any(sat != hub for sat in link_satellites):
                raise Exception(
                    "Link table can only be joined with itself (self-join) or satellite tables"
                )

    hash_pk = "Hash" + "".join(primary_keys)
    date_adjust = (
        "(_LOAD_DTS - INTERVAL 1 DAY) as adjusted_date"
        if report_type == "daily_business_report"
        else "_LOAD_DTS as adjusted_date"
    )

    # Get hub/link table
    if hub.startswith("lnk"):
        hub_query = f"""
        SELECT DISTINCT {hash_pk}
        FROM (
            SELECT {hash_pk}, {date_adjust}
            FROM {catalog}.silver.{hub}
        )
        """
        hub_table = spark.sql(hub_query)
    else:
        hub_query = f"""
        SELECT {hash_pk}, {", ".join(primary_keys)}
        FROM (
            SELECT {hash_pk}, {", ".join(primary_keys)}, {date_adjust}
            FROM {catalog}.silver.{hub}
        )
        """
        hub_table = spark.sql(hub_query)

    # SCD1
    if int(scd_type) == 1:
        df = hub_table
        for satellite in satellites:
            # Get column names excluding system columns
            sat_columns = [
                col
                for col in spark.table(f"{catalog}.silver.{satellite}").columns
                if col not in [hash_pk, "_LOAD_DTS", "_REC_SRC", "_HASH_DIFF"]
            ]

            # Add prefix only if enabled
            if prefix_satellite_columns:
                sat_columns_select = [f"{col} as {satellite}_{col}" for col in sat_columns]
            else:
                sat_columns_select = sat_columns

            sat_query = f"""
            WITH base_sat AS (
                SELECT *, {date_adjust}
                FROM {catalog}.silver.{satellite}
            )
            SELECT 
                {hash_pk},
                {", ".join(sat_columns_select)},
                adjusted_date as _{satellite}_LOAD_DTS
            FROM base_sat
            """
            sat_table = spark.sql(sat_query)

            # Join and rank for this satellite
            sat_latest = (
                sat_table.withColumn(
                    "_RANK",
                    row_number().over(
                        Window.partitionBy(hash_pk).orderBy(desc(f"_{satellite}_LOAD_DTS"))
                    ),
                )
                .filter(col("_RANK") == 1)
                .drop("_RANK")
            )

            df = df.join(sat_latest, on=hash_pk, how=join_type)

        load_dts_columns = [c for c in df.columns if c.endswith("_LOAD_DTS")]
        if len(load_dts_columns) > 1:
            df = df.withColumn("_LOAD_DTS", greatest(*[col(c) for c in load_dts_columns]))
            df = df.drop(*load_dts_columns)
        elif len(load_dts_columns) == 1:
            df = df.withColumnRenamed(load_dts_columns[0], "_LOAD_DTS")

        df = df.drop(hash_pk)

    # SCD2
    elif int(scd_type) == 2:
        df = _get_pit_df(spark, catalog, satellites, primary_keys, report_type)

        for satellite in satellites:
            # Get column names excluding system columns
            sat_columns = [
                col
                for col in spark.table(f"{catalog}.silver.{satellite}").columns
                if col not in [hash_pk, "_LOAD_DTS", "_REC_SRC", "_HASH_DIFF"]
            ]

            # Add prefix only if enabled
            if prefix_satellite_columns:
                sat_columns_select = [f"{col} as {satellite}_{col}" for col in sat_columns]
            else:
                sat_columns_select = sat_columns

            sat_query = f"""
            WITH base_sat AS (
                SELECT *, {date_adjust}
                FROM {catalog}.silver.{satellite}
            )
            SELECT 
                {hash_pk},
                {", ".join(sat_columns_select)},
                adjusted_date as {satellite}_LOAD_DTS
            FROM base_sat
            """
            sat_table = spark.sql(sat_query)

            df = df.join(sat_table, on=[hash_pk, f"{satellite}_LOAD_DTS"], how=join_type).drop(
                f"{satellite}_LOAD_DTS"
            )

        end_date = (
            expr("current_date() - INTERVAL 1 DAY")
            if report_type == "daily_business_report"
            else current_date()
        )

        df = (
            df.join(hub_table, on=hash_pk)
            .drop(hash_pk)
            .withColumn("EffectiveFrom", to_date("EffectiveFrom"))
            .withColumn(
                "EffectiveTo",
                when(col("EffectiveTo").isNull(), end_date).otherwise(to_date("EffectiveTo")),
            )
        )

    else:
        raise Exception("Invalid SCD Type")

    return df


def get_relationship_table(
    spark, catalog, link, primary_keys, groupby_keys, scd_type, report_type=None
):
    """
    Creates a relationship table from a link table using SCD Type 1 or 2 patterns,
    establishing relationships between business entities while maintaining temporal validity.

    Parameters:
        spark (SparkSession): SparkSession object for database operations
        catalog (str): Database catalog name containing the tables
        link (str): Name of the link table (must start with 'lnk')
        primary_keys (list): List of primary key columns to select from link table
        groupby_keys (list): List of columns to group by for determining relationship changes
        scd_type (int): Type of Slowly Changing Dimension pattern (1 or 2)
        report_type (str): Expect "daily_business_report" or None, this is used to globally apply a logic to reduce date by 1 from _LOAD_DTS and all derivative columns from _LOAD_DTS. If "BusinessReportEffectiveDate" is provided and the given lnk table have a column BusinessReportEffectiveDate, it would also undergo the logic to reduce date by 1.

    Requirements:
        - Link table name must start with 'lnk'
        - primary_keys list cannot be empty
        - groupby_keys list cannot be empty
        - All groupby_keys must exist in primary_keys
        - groupby_keys must be a proper subset of primary_keys

    Example Usage:
        # Setup
        primary_keys = ["EmployeeID", "DeptID", "RoleID"]
        groupby_keys = ["EmployeeID"]

        # Input Link Table:
        HashEmployeeIdDeptIdRoleId  HashEmployeeId  HashDeptId  HashRoleId  EmployeeID  DeptID  RoleID  _LOAD_DTS
        xyz123                      abc111          def111      ghi111      E1          D1      R1      2023-01-01  # Initial hire
        xyz124                      abc111          def111      ghi222      E1          D1      R2      2023-03-01  # Role change
        xyz125                      abc111          def222      ghi222      E1          D2      R2      2023-06-01  # Dept transfer
        xyz321                      abc222          def111      ghi111      E2          D1      R1      2023-01-01  # Another employee

        # SCD Type 1 Output (Current State):
        EmployeeID  DeptID  RoleID
        E1          D2      R2      # Latest state
        E2          D1      R1      # Latest state

        # SCD Type 2 Output (Historical):
        EmployeeID  DeptID  RoleID  EffectiveFrom  EffectiveTo
        E1          D1      R1      2023-01-01     2023-03-01  # Initial state
        E1          D1      R2      2023-03-01     2023-06-01  # Role change
        E1          D2      R2      2023-06-01     9999-12-31  # Dept change
        E2          D1      R1      2023-01-01     9999-12-31  # Single state

    Returns:
        DataFrame: Relationship table with:
            - Selected primary key columns
            For SCD Type 1:
                - Latest valid relationships grouped by groupby_keys
            For SCD Type 2:
                - EffectiveFrom: Start date of relationship validity
                - EffectiveTo: End date of relationship validity

    Implementation Details:
        SCD Type 1:
            - Uses window function to get latest record per groupby_keys
            - Removes temporal columns from output

        SCD Type 2:
            - Calculates EffectiveFrom and EffectiveTo dates
            - Maintains complete history of changes
            - Orders output by groupby_keys and EffectiveFrom
    """
    # Input validation
    if not link.startswith("lnk"):
        raise ValueError("Table name must start with 'lnk'")

    if not primary_keys:
        raise ValueError("primary_keys list cannot be empty")

    if not groupby_keys:
        raise ValueError("groupby_keys list cannot be empty")

    if not all(key in primary_keys for key in groupby_keys):
        raise ValueError("All groupby_keys must be present in primary_keys")

    if len(groupby_keys) >= len(primary_keys):
        raise ValueError(
            "groupby_keys must be a subset of primary_keys (less than or equal to primary_keys)"
        )

    # Adjust load date based on report_type
    date_adjust = (
        "(_LOAD_DTS - INTERVAL 1 DAY) as adjusted_date"
        if report_type == "daily_business_report"
        else "_LOAD_DTS as adjusted_date"
    )

    # Get link table with required columns
    link_query = f"""
    SELECT 
        {", ".join(primary_keys)},
        {date_adjust}
    FROM {catalog}.silver.{link}
    """
    link_table = spark.sql(link_query)

    # SCD Type 1 Implementation
    if int(scd_type) == 1:
        window_spec = Window.partitionBy(groupby_keys).orderBy(desc("adjusted_date"))

        df = (
            link_table.withColumn("row_num", row_number().over(window_spec))
            .filter(col("row_num") == 1)
            .drop("row_num", "adjusted_date")
        )

    # SCD Type 2 Implementation
    elif int(scd_type) == 2:
        window_spec = Window.partitionBy(groupby_keys).orderBy("adjusted_date")

        # Set end_date based on report_type
        end_date = (
            expr("current_date() - INTERVAL 1 DAY")
            if report_type == "daily_business_report"
            else current_date()
        )

        # Calculate effective dates based on link table changes
        df = (
            link_table.withColumn("EffectiveFrom", to_date("adjusted_date"))
            .withColumn(
                "EffectiveTo",
                when(lead("adjusted_date").over(window_spec).isNull(), end_date).otherwise(
                    to_date(lead("adjusted_date").over(window_spec))
                ),
            )
            .drop("adjusted_date")
        )

        # Sort by groupby keys and EffectiveFrom
        df = df.orderBy(groupby_keys + ["EffectiveFrom"])

    else:
        raise ValueError("Invalid SCD Type. Must be 1 or 2")

    # Check if BusinessReportEffectiveDate exists in the table
    table_columns = spark.sql(f"DESCRIBE {catalog}.silver.{link}").select("col_name").collect()
    has_business_report_date = any(
        row.col_name == "BusinessReportEffectiveDate" for row in table_columns
    )

    if has_business_report_date and report_type == "daily_business_report":
        df = df.withColumn(
            "BusinessReportEffectiveDate", expr("(BusinessReportEffectiveDate - INTERVAL 1 DAY)")
        )

    return df


def validate_before_write(df, meta, pk, table_name):
    """
    Validates a DataFrame against specified metadata rules before writing to ensure data quality.
    This function performs multiple validation checks including primary key uniqueness,
    null value thresholds, column distinctness, and schema validation.

    For example, validating a customer dimension table:
    Input DataFrame:
    CustomerID  Name    Status  EffectiveFrom  EffectiveTo
    C1         John    Active  2023-01-01     2023-02-01
    C1         John    Active  2023-02-01     9999-12-31
    C2         Jane    Active  2023-01-01     9999-12-31

    Input Metadata:
    meta = {
        "null": {
            "Name": [[0, 10], None],  # Allow 0-10 nulls, no condition
            "Status": [[0, 0], "Name IS NOT NULL"]  # No nulls allowed where Name is not null
        },
        "distinct": {
            "CustomerID,EffectiveFrom": None  # These columns combined should be unique
        },
        "column_name": ["CustomerID", "Name", "Status", "EffectiveFrom", "EffectiveTo"]
    }

    Args:
        df: DataFrame to validate
        meta: Dictionary containing validation rules:
            "null": Dict of column names with [[min_nulls, max_nulls], filter_condition]
            "distinct": Dict of comma-separated column names that should be unique
            "column_name": List of expected column names
        pk: Primary key column(s) as string or list
        table_name: Name of the table, used to determine specific validation rules

    Raises:
        AssertionError: If any validation fails, with specific error messages:
            - "{pk} Not Distinct!" - Primary key uniqueness violation
            - "{column} Null Count [{count}] Exceed Threshold [{threshold}]!" - Null check violation
            - "{columns} Not Distinct!" - Uniqueness constraint violation
            - "Column Name Mismatch!" - Schema validation failure

    Example Usage:
        meta = {
            "null": {
                "CustomerName": [[0, 0], None],  # No nulls allowed
                "Status": [[0, 10], "CustomerType = 'VIP'"]  # Max 10 nulls for VIP customers
            },
            "distinct": {
                "CustomerID,BusinessDate": None  # Composite uniqueness
            },
            "column_name": ["CustomerID", "CustomerName", "Status", "BusinessDate"]
        }

        validate_before_write(
            df=customer_df,
            meta=meta,
            pk="CustomerID",
            table_name="dim_customer"
        )

    Notes:
        - For dimension tables (table_name starting with "dim"):
          - Checks primary key uniqueness with EffectiveFrom if present
          - Otherwise checks primary key uniqueness alone
        - Null validations can include conditional filters
        - Distinct checks can be performed on multiple columns combined
        - Schema validation ensures exact column name matches
    """
    if table_name.startswith("dim"):
        if "EffectiveFrom" in df.columns:
            assert df.select("EffectiveFrom", *pk).distinct().count() == df.count(), (
                f"{pk} Not Distinct!"
            )
        else:
            assert df.select(*pk).distinct().count() == df.count(), f"{pk} Not Distinct!"
    for key, value in meta.items():
        if key == "null":
            for c, v in value.items():
                v[0][1] += 1
                if v[1]:
                    count = df.filter(v[1]).filter(col(c).isNull()).count()
                else:
                    count = df.filter(col(c).isNull()).count()
                assert count in range(*v[0]), (
                    f"{c} Null Count [{count}] Exceed Threshold [{v[0][1]}]!"
                )
        elif key == "distinct":
            for c, _ in value.items():
                c = [x.strip() for x in c.split(",")]
                assert df.select(*c).distinct().count() == df.count(), f"{c} Not Distinct!"
        elif key == "column_name":
            assert set(df.columns) == set(value), "Column Name Mismatch!"


def create_temporal_view(
    spark,
    df,
    primary_keys,
    granularity="monthly",  # Options: daily, weekly, monthly, quarterly, yearly
    effective_from_col="EffectiveFrom",
    effective_to_col="EffectiveTo",
    filter_by_col=None,
):
    """
    Transforms an SCD2 (Slowly Changing Dimension Type 2) table into a point-in-time reporting view.
    This function takes a dataframe containing temporal data with effective dates (start/end dates)
    and converts it into a standardized reporting format at the specified time granularity.

    For example, if you have employee position changes:
    Input SCD2 Data:
    EmpID  Position  EffectiveFrom  EffectiveTo
    101    Analyst   2023-01-15     2023-03-20
    101    Senior    2023-03-20     2023-06-10
    101    Lead      2023-06-10     9999-12-31

    Output with monthly granularity:
    EmpID  Position  ReportDate    Year  Month  Quarter
    101    Analyst   2023-01-31    2023  1     2023Q1
    101    Analyst   2023-02-28    2023  2     2023Q1
    101    Senior    2023-03-31    2023  3     2023Q1
    101    Senior    2023-04-30    2023  4     2023Q2
    101    Senior    2023-05-31    2023  5     2023Q2
    101    Lead      2023-06-30    2023  6     2023Q2
    ...

    Args:
        spark: SparkSession object for database operations
        df: Input DataFrame containing SCD2 data with effective dates
        primary_keys: List of columns that uniquely identify an entity
        granularity: Time period for the view:
            - 'daily': Every day
            - 'weekly': Last day of each week (Sunday)
            - 'monthly': Last day of each month
            - 'quarterly': Last day of each quarter (Mar 31, Jun 30, Sep 30, Dec 31)
            - 'yearly': Last day of each year (Dec 31)
        effective_from_col: Column name for the start date
        effective_to_col: Column name for the end date
        filter_by_col: Optional timestamp or date column to filter the data based on max of that column with groupby of he primary_keys

    Returns:
        DataFrame with one row per entity per time period based on specified granularity.
        Additional columns:
        - ReportDate: Last day of the respective period
        - Year: Calendar year
        - Month: Month number (1-12)
        - Quarter: Year and quarter (e.g., "2023Q1")
        - WeekEndDate: Last day of week (if weekly granularity)
        - Max{filter_by_col} groupby given primary key (if filter_by_col is provided)
        - MaxEffectiveTo (if filter_by_col is provided)

    Example Usage:
        # Monthly view (last day of each month)
        monthly_df = create_temporal_view(
            employee_df,
            primary_keys=["EmployeeId"],
            granularity="monthly"
        )
    """

    # Validate granularity
    valid_granularities = ["daily", "weekly", "monthly", "quarterly", "yearly"]
    granularity = granularity.lower()
    if granularity not in valid_granularities:
        raise ValueError(f"granularity must be one of {valid_granularities}")

    # Find date range
    min_date = df.select(min(effective_from_col)).collect()[0][0]

    max_date = df.select(
        when(max(effective_to_col) > current_date(), current_date()).otherwise(
            max(effective_to_col)
        )
    ).collect()[0][0]

    # Create comprehensive date table
    date_sql = f"""
    SELECT 
        date as daily_date,
        CAST(date_trunc('week', date) + interval 6 days AS DATE) as weekly_date,
        last_day(date) as monthly_date,
        last_day(add_months(date_trunc('quarter', date), 2)) as quarterly_date,
        last_day(add_months(date_trunc('year', date), 11)) as yearly_date
    FROM (
        SELECT explode(sequence(
            to_date('{min_date}'),
            to_date('{max_date}'),
            interval 1 day
        )) as date
    )
    """

    # Create date spine
    date_df = spark.sql(date_sql)

    # Join with original data first
    result_df = (
        date_df.join(
            df,
            on=[
                date_df.daily_date >= col(effective_from_col),
                date_df.daily_date <= col(effective_to_col),
            ],
        )
        .withColumn(
            "row_num",
            row_number().over(
                Window.partitionBy(*primary_keys, f"{granularity}_date").orderBy(
                    col(effective_from_col).desc()
                )
            ),
        )
        .filter(col("row_num") == 1)
    )

    # Select appropriate date column and add period indicators based on granularity
    result_df = (
        result_df.select(
            *[
                c
                for c in result_df.columns
                if c not in ["row_num"] + [f"{g}_date" for g in valid_granularities]
            ],
            col(f"{granularity}_date").alias("ReportDate"),
        )
        .withColumn("ReportDateYear", year(col("ReportDate")))
        .withColumn("ReportDateMonth", month(col("ReportDate")))
        .withColumn(
            "ReportDateQuarter",
            concat(
                when(month(col("ReportDate")) >= 4, year(col("ReportDate"))).otherwise(
                    year(col("ReportDate")) - 1
                ),
                lit("Q"),
                when(month(col("ReportDate")).between(4, 6), 1)
                .when(month(col("ReportDate")).between(7, 9), 2)
                .when(month(col("ReportDate")).between(10, 12), 3)
                .otherwise(4),
            ),
        )
    )

    # Add week number if weekly granularity
    if granularity.lower() == "weekly":
        result_df = result_df.withColumn("ReportDateWeekNumber", weekofyear(col("ReportDate")))

    if filter_by_col:
        # Get the maximum EffectiveTo date for the entire dataset
        max_effective_to = df.agg(max(effective_to_col)).collect()[0][0]

        # Create window spec for partitioning by primary keys
        window_spec = Window.partitionBy(*primary_keys)

        # Add filter with modified logic
        result_df = (
            result_df.withColumn(f"Max{filter_by_col}", max(filter_by_col).over(window_spec))
            .withColumn("MaxEffectiveTo", lit(max_effective_to))
            .withColumn(
                "should_include",
                (col("ReportDate") <= col(f"Max{filter_by_col}"))
                | (
                    (year(col(f"Max{filter_by_col}")) == year(lit(max_effective_to)))
                    & (month(col(f"Max{filter_by_col}")) == month(lit(max_effective_to)))
                ),
            )
            .filter(col("should_include"))
            .drop("should_include", filter_by_col)
        )

    return result_df


# This is the upgraded version of merge_scd2_tables
def merge_temporal_views(
    df1,
    df2,
    join_keys,
    dup_cols=[],
    report_date_col="ReportDate",
    join_type="left",
    alias1="df1",
    alias2="df2",
):
    """
    Merges two temporal views that have already been denormalized using create_temporal_view.
    This function performs a join on the join keys and report date, handling specified duplicate
    columns by giving priority to df2 values when not null.

    For example, merging denormalized customer and address views:
    Input View 1 (Customer):
    CustomerID  Status  UpdatedBy  ReportDate  Year  Month  Quarter
    C1         Active  UserA      2023-01-31  2023  1      2023Q1
    C1         Active  UserA      2023-02-28  2023  2      2023Q1
    C1         Active  UserA      2023-03-31  2023  3      2023Q1

    Input View 2 (Address):
    CustomerID  City      UpdatedBy  ReportDate  Year  Month  Quarter
    C1         New York  UserB      2023-01-31  2023  1      2023Q1
    C1         Boston    null       2023-02-28  2023  2      2023Q1
    C1         Boston    UserC      2023-03-31  2023  3      2023Q1

    Output (with dup_cols=["UpdatedBy"]):
    CustomerID  Status  City      UpdatedBy  ReportDate  Year  Month  Quarter
    C1         Active  New York  UserB      2023-01-31  2023  1      2023Q1
    C1         Active  Boston    UserA      2023-02-28  2023  2      2023Q1  # Uses df1.UpdatedBy since df2.UpdatedBy is null
    C1         Active  Boston    UserC      2023-03-31  2023  3      2023Q1

    Args:
        df1: First temporal view DataFrame (output from create_temporal_view)
        df2: Second temporal view DataFrame (output from create_temporal_view)
        join_keys: List of columns to join the tables on (e.g., ["CustomerID"])
        dup_cols: List of columns that appear in both tables that should be handled.
                 For these specified columns:
                 - If df2 value is not null, use df2's value
                 - If df2 value is null, use df1's value
                 Common examples: ["UpdatedBy", "UpdatedDate", "Source"]
                 Note: The function does not automatically detect duplicate columns;
                 they must be explicitly listed here
        report_date_col: Name of the report date column (default: "ReportDate")
        join_type: Type of join to perform ("left", "right", "inner", "outer", default: "left")
        alias1: Alias for first DataFrame (default: "df1")
        alias2: Alias for second DataFrame (default: "df2")

    Returns:
        DataFrame containing:
        - All columns from both input tables
        - For columns specified in dup_cols:
          - Uses df2's value if it's not null
          - Falls back to df1's value if df2's value is null
        - ReportDate and other temporal columns (Year, Month, Quarter)
        - Drops duplicate join keys from df2

    Example Usage:
        # First create temporal views with same granularity
        customer_view = create_temporal_view(
            customer_df,
            primary_keys=["CustomerID"],
            granularity="monthly"
        )
        address_view = create_temporal_view(
            address_df,
            primary_keys=["CustomerID"],
            granularity="monthly"  # Must match df1's granularity
        )

        # Then merge the views, specifying which columns are duplicated
        merged_view = merge_temporal_views(
            df1=customer_view,
            df2=address_view,
            join_keys=["CustomerID"],
            dup_cols=["UpdatedBy", "UpdatedDate"],  # Must list all duplicate columns to handle
            join_type="inner"
        )

    Notes:
        - Both input DataFrames must be outputs from create_temporal_view
        - Both DataFrames must be created with the same granularity
          (e.g., both "monthly" or both "weekly")
        - Duplicate columns must be explicitly listed in dup_cols parameter
        - The function does not automatically detect duplicate columns
        - Join types:
          - "left": Keep all rows from df1 (default)
          - "right": Keep all rows from df2
          - "inner": Keep only matching rows
          - "outer": Keep all rows from both tables
    """
    # Check if both dataframes have the required temporal columns
    required_cols = [
        report_date_col,
        "ReportDateYear",
        "ReportDateMonth",
        "ReportDateQuarter",
        "EffectiveFrom",
        "EffectiveTo",
    ]

    # Add ReportDateWeekNumber to required_cols if it exists in df1
    if "ReportDateWeekNumber" in df1.columns:
        required_cols.append("ReportDateWeekNumber")

    df1_cols = df1.columns
    df2_cols = df2.columns

    missing_cols_df1 = [col for col in required_cols if col not in df1_cols]
    missing_cols_df2 = [col for col in required_cols if col not in df2_cols]

    if missing_cols_df1:
        raise ValueError(f"DataFrame 1 is missing required temporal columns: {missing_cols_df1}")
    if missing_cols_df2:
        raise ValueError(f"DataFrame 2 is missing required temporal columns: {missing_cols_df2}")

    # First, create the join condition
    join_condition = []
    for join_key in join_keys:
        join_condition.append(col("df1." + join_key) == col("df2." + join_key))
    join_condition.append(col("df1." + report_date_col) == col("df2." + report_date_col))

    # Perform the join
    df = df1.alias("df1").join(df2.alias("df2"), join_condition, how=join_type)

    # Create a list of columns to select, starting with non-duplicate columns from df1
    select_cols = []

    # Add temporal columns with proper handling for full outer join
    select_cols.extend(
        [
            coalesce(col("df1." + report_date_col), col("df2." + report_date_col)).alias(
                report_date_col
            ),
            coalesce(col("df1.ReportDateYear"), col("df2.ReportDateYear")).alias("ReportDateYear"),
            coalesce(col("df1.ReportDateMonth"), col("df2.ReportDateMonth")).alias(
                "ReportDateMonth"
            ),
            coalesce(col("df1.ReportDateQuarter"), col("df2.ReportDateQuarter")).alias(
                "ReportDateQuarter"
            ),
            greatest(
                coalesce(col("df1.EffectiveFrom"), col("df2.EffectiveFrom")),
                coalesce(col("df2.EffectiveFrom"), col("df1.EffectiveFrom")),
            ).alias("EffectiveFrom"),
            least(
                coalesce(col("df1.EffectiveTo"), col("df2.EffectiveTo")),
                coalesce(col("df2.EffectiveTo"), col("df1.EffectiveTo")),
            ).alias("EffectiveTo"),
        ]
    )

    # Add ReportDateWeekNumber if it exists in df1
    if "ReportDateWeekNumber" in df1.columns:
        select_cols.append(
            coalesce(col("df1.ReportDateWeekNumber"), col("df2.ReportDateWeekNumber")).alias(
                "ReportDateWeekNumber"
            )
        )

    # Add join keys with coalesce
    for key in join_keys:
        select_cols.append(coalesce(col("df1." + key), col("df2." + key)).alias(key))

    # Add remaining columns from df1 that aren't in df2 and aren't temporal or join keys
    df1_remaining_cols = [
        c
        for c in df1.columns
        if c not in required_cols and c not in join_keys and c not in dup_cols
    ]
    for col_name in df1_remaining_cols:
        select_cols.append(col("df1." + col_name).alias(col_name))

    # Add unique columns from df2
    df2_unique_cols = [
        c
        for c in df2.columns
        if c not in required_cols and c not in join_keys and c not in df1.columns
    ]
    for col_name in df2_unique_cols:
        select_cols.append(col("df2." + col_name).alias(col_name))

    # Handle duplicate columns
    for dup_col in dup_cols:
        select_cols.append(
            when(col("df2." + dup_col).isNotNull(), col("df2." + dup_col))
            .otherwise(col("df1." + dup_col))
            .alias(dup_col)
        )

    # Select only the columns we want
    df = df.select(select_cols)

    return df


def create_temporal_business_view(df, effective_to_col="EffectiveTo", granularity="monthly"):
    """
    Creates a business view of temporal data by adjusting the ReportDate based on the maximum EffectiveTo date.
    Supports different time granularities for flexible business reporting needs.

    For example:
    Input DataFrame (Monthly):
    EmployeeID  ReportDate  ReportDateYear  ReportDateMonth  ReportDateQuarter  ReportDateWeekNumber  EffectiveFrom  EffectiveTo
    E1         2024-01-31  2024            1               2024Q1             5                    2024-01-01     2024-02-15
    E1         2024-02-28  2024            2               2024Q1             9                    2024-02-15     2024-02-15

    Output DataFrame (Monthly):
    EmployeeID  ReportDate  ReportDateYear  ReportDateMonth  ReportDateQuarter  ReportDateWeekNumber  EffectiveFrom  EffectiveTo
    E1         2024-01-31  2024            1               2024Q1             5                    2024-01-01     2024-02-15
    E1         2024-02-15  2024            2               2024Q1             9                    2024-02-15     2024-02-15

    Args:
        df: Input DataFrame containing temporal columns:
           - ReportDate: Date of the record
           - ReportDateYear: Year component of ReportDate
           - ReportDateMonth: Month component of ReportDate (required for monthly granularity)
           - ReportDateQuarter: Quarter component of ReportDate (required for quarterly granularity)
           - ReportDateWeekNumber: Week number component of ReportDate (required for weekly granularity)
           - EffectiveFrom: Start date of record validity
           - EffectiveTo: End date of record validity
        effective_to_col: The column that contains the end date of record validity (default: "EffectiveTo")
        granularity: Time period for the view (default: "monthly"):
           - 'daily': No modification needed (returns original DataFrame)
           - 'weekly': Match by year and week number
           - 'monthly': Match by year and month
           - 'quarterly': Match by year and quarter
           - 'yearly': Match by year

    Returns:
        DataFrame with adjusted ReportDate values where:
        - For daily granularity: Returns original DataFrame without modifications
        - For other granularities: Records in the final period use EffectiveTo as their ReportDate
        - All other records maintain their original ReportDate

    Example Usage:
        # Create monthly business view
        monthly_view = create_temporal_business_view(df, granularity="monthly")

        # Create quarterly business view
        quarterly_view = create_temporal_business_view(df, granularity="quarterly")

        # Daily view (returns original DataFrame)
        daily_view = create_temporal_business_view(df, granularity="daily")

    Notes:
        - Daily granularity returns the original DataFrame without modifications
        - Function requires appropriate temporal columns based on chosen granularity
        - Only modifies ReportDate for records in the most recent period
        - Preserves all other temporal attributes
        - Does not modify data for historical periods
    """
    # Validate granularity
    valid_granularities = ["daily", "weekly", "monthly", "quarterly", "yearly"]
    if granularity not in valid_granularities:
        raise ValueError(f"granularity must be one of {valid_granularities}")

    # Define required columns for each granularity
    base_columns = {"ReportDate", "ReportDateYear", "EffectiveFrom", "EffectiveTo"}

    granularity_columns = {
        "daily": set(),  # No additional columns needed
        "weekly": {"ReportDateWeekNumber"},
        "monthly": {"ReportDateMonth"},
        "quarterly": {"ReportDateQuarter"},
        "yearly": set(),  # No additional columns needed beyond base columns
    }

    # Get required columns for specified granularity
    required_columns = base_columns | granularity_columns[granularity]

    # Check for missing columns
    df_columns = set(df.columns)
    missing_columns = required_columns - df_columns

    if missing_columns:
        raise ValueError(
            f"Missing required columns for {granularity} granularity: {sorted(missing_columns)}"
            f"Required columns: {sorted(required_columns)}"
            f"Found columns: {sorted(df_columns)}"
        )

    # For daily granularity, return original DataFrame
    if granularity == "daily":
        return df

    # Get the actual maximum EffectiveTo date value
    max_effective_to = df.agg(max(col(effective_to_col))).collect()[0][0]

    # Extract year, month from max_effective_to
    max_year = year(lit(max_effective_to))
    max_month = month(lit(max_effective_to))
    max_week = weekofyear(lit(max_effective_to))

    # Calculate fiscal year and quarter using the same logic
    max_fiscal_quarter = concat(
        when(max_month >= 4, max_year).otherwise(max_year - 1),
        lit("Q"),
        when(max_month.between(4, 6), 1)
        .when(max_month.between(7, 9), 2)
        .when(max_month.between(10, 12), 3)
        .otherwise(4),
    )

    # Update ReportDate based on granularity
    if granularity == "weekly":
        df = df.withColumn(
            "ReportDate",
            when(
                (col("ReportDateYear") == max_year) & (col("ReportDateWeekNumber") == max_week),
                lit(max_effective_to),
            ).otherwise(col("ReportDate")),
        )

    elif granularity == "monthly":
        df = df.withColumn(
            "ReportDate",
            when(
                (col("ReportDateYear") == max_year) & (col("ReportDateMonth") == max_month),
                lit(max_effective_to),
            ).otherwise(col("ReportDate")),
        )

    elif granularity == "quarterly":
        df = df.withColumn(
            "ReportDate",
            when(col("ReportDateQuarter") == max_fiscal_quarter, lit(max_effective_to)).otherwise(
                col("ReportDate")
            ),
        )

    elif granularity == "yearly":
        max_fiscal_year = when(max_month >= 4, max_year).otherwise(max_year - 1)
        df = df.withColumn(
            "ReportDate",
            when(col("ReportDateYear") == max_fiscal_year, lit(max_effective_to)).otherwise(
                col("ReportDate")
            ),
        )

    return df


def create_latest_temporal_view(df, report_date_col="ReportDate"):
    """
    Creates a view containing only the latest records from a temporal view DataFrame.
    This function takes the output from create_temporal_view and returns only the records
    from the most recent ReportDate.

    For example, if you have temporal employee position data:
    Input Temporal View:
    EmpID  Position  ReportDate  Year  Month  Quarter
    101    Analyst   2023-01-31  2023  1      2022Q4
    101    Analyst   2023-02-28  2023  2      2022Q4
    101    Senior    2023-03-31  2023  3      2022Q4
    102    Manager   2023-01-31  2023  1      2022Q4
    102    Director  2023-03-31  2023  3      2022Q4

    Output Latest View (as of 2023-03-31):
    EmpID  Position  ReportDate  Year  Month  Quarter
    101    Senior    2023-03-31  2023  3      2022Q4
    102    Director  2023-03-31  2023  3      2022Q4

    Args:
        df: Input DataFrame from create_temporal_view
        report_date_col: Column name containing the report date (default: "ReportDate")

    Returns:
        DataFrame containing only the records from the latest ReportDate
    """

    latest_df = df.filter(col(report_date_col) == df.select(max(report_date_col)).collect()[0][0])

    return latest_df


def format_table(
    spark,
    df,
    catalog,
    pk,
    debug=False,
    rename={},
    schema_name="gold",
    table_name="",
    validate={},
    write=False,
):
    """
    Formats and validates a DataFrame before writing to a target table. This function handles
    column formatting, renaming, sorting, validation and writing to a Unity Catalog table.

    For example, formatting a customer dimension table:
    Input DataFrame:
    customer_id  first_name  last_name  birth_date_id  status
    1           John        Smith      20230101       A
    2           Jane        Doe        20230102       B

    Output DataFrame (after formatting):
    BirthDateId  CustomerId  FirstName  LastName  Status
    20230101    1          John       Smith     A
    20230102    2          Jane       Doe       B

    Args:
        spark: SparkSession object
        df: Input DataFrame to format
        catalog: Unity Catalog name where table will be written
        pk: Primary key column(s) for sorting
        debug: If True, displays DataFrame and creates temp view (default: False)
        rename: Dictionary of column renames {old_name: new_name} (default: empty dict)
        schema_name: Target schema name (default: "gold")
        table_name: Target table name, must start with dim_/fact_/ref_/mst_
        validate: Dictionary of validation rules (see validate_before_write docs)
        write: If True, writes DataFrame to Unity Catalog (default: False)

    Returns:
        Formatted DataFrame with:
        - Standardized Id columns (cast to int for date IDs)
        - Renamed columns as specified
        - Columns sorted alphabetically
        - Rows sorted by primary key

    Raises:
        Exception: If table_name doesn't start with dim_/fact_/ref_/mst_

    Example Usage:
        formatted_df = format_table(
            spark=spark,
            df=customer_df,
            catalog="retail",
            pk="CustomerId",
            rename={
                "customer_id": "CustomerId",
                "first_name": "FirstName"
            },
            table_name="dim_customer",
            validate={
                "null": {
                    "CustomerId": [[0, 0], None]  # No nulls allowed
                },
                "distinct": {
                    "CustomerId": None  # Must be unique
                }
            },
            write=True
        )

    Notes:
        1. Column Formatting Rules:
           - Columns ending with 'Id':
             - If contains 'Date': Cast to integer (e.g., BirthDateId)
             - Otherwise: Left as is

        2. Table Naming Conventions:
           - dim_*: Dimension tables
           - fact_*: Fact tables
           - ref_*: Reference tables
           - mst_*: Master tables

        3. Debug Mode Features:
           - Displays DataFrame contents
           - Creates temporary view with table_name
           - Useful for testing and development

        4. Write Mode:
           - Uses overwrite mode
           - Allows schema evolution
           - Writes to Unity Catalog path: {catalog}.{schema_name}.{table_name}
    """
    if schema_name == "gold" and not any(
        [
            "dim_" in table_name,
            "fact_" in table_name,
        ]
    ):
        raise Exception("Invalid Table Name - gold schema tables must start with dim_ or fact_")

    # Format ID columns
    for column in df.columns:
        # Cast date IDs to integer
        if column.endswith("Id"):
            if "Date" in column:
                df = df.withColumn(column, col(column).cast("int"))

    # Apply column renames
    for k, v in rename.items():
        df = df.withColumnRenamed(k, v)

    # Sort columns alphabetically and rows by primary key
    df = df.select(sorted(df.columns)).sort(pk)

    # Debug mode operations
    if debug:
        display(df)
        df.createOrReplaceTempView(table_name)

    # Validate data quality
    validate_before_write(df, validate, pk, table_name)

    # Write to Unity Catalog if requested
    if write:
        df.write.option("overwriteSchema", "True").mode("overwrite").saveAsTable(
            f"{catalog}.{schema_name}.{table_name}"
        )
    return df
