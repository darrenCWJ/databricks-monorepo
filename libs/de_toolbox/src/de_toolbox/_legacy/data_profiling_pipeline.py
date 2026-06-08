from datetime import datetime
from functools import reduce

from pyspark.sql.functions import (
    avg,
    col,
    count,
    explode,
    length,
    lit,
    max,
    min,
    size,
    stddev,
    to_date,
    when,
)
from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    FloatType,
    IntegerType,
    LongType,
    MapType,
    NumericType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)


def profile_data(df, max_depth=0, compute_all=False, parent=None):
    """Iterate through the dataset and calculate statistics for each field and subfield.
        Recommend to only take latest data instead of entire dataset as all rows of data are utilised in the computing of statistics.

    Params:
        df: DataFrame for dataset
        max_depth: Recursion depth for fields and subfields. Use 0 for only the basic fields and any integer greater than 0 for desired subfield levels. If None, recurses until all subfields are obtained. Default 0.
        compute_all: Whether to compute all statistics. If True does full suite of statistics computation for each field. If False, only computes dtype, total count of rows, filled row counts, null row counts and sparsness of data for each field. Default is False.
        parent: Parent field name (only applicable for subfields)

    Returns:
        Dictionary containing each field and subfield as a separate key and their statistics.
        Subfields will be named as such: {parent_field_name}~{subfield_name}, each tilda represents a level of depth.
    """

    stats_dict = {}
    schema = df.schema

    for field in schema.fields:
        field_name = field.name
        full_field_name = f"{parent}~{field.name}" if parent else field.name
        field_type = field.dataType

        if isinstance(field_type, StructType):
            stats_dict[full_field_name] = compute_stats(
                df, field_name, field_type, compute_all, parent
            )
            nested_df = df.select(col(field_name + ".*"))

            # Compute stats for subfields
            if max_depth is None or max_depth > 0:
                new_depth = None if max_depth is None else max_depth - 1
                stats_dict.update(profile_data(nested_df, new_depth, compute_all, full_field_name))

        elif isinstance(field_type, MapType):
            stats_dict[full_field_name] = compute_stats(
                df, field_name, field_type, compute_all, full_field_name
            )
            value_type = field_type.valueType

            # Compute stats for subfields
            if max_depth is None or max_depth > 0:
                new_depth = None if max_depth is None else max_depth - 1
                exploded_df = df.select(explode(col(field_name)).alias("key", "value"))

                # Compute stats for each key in the map
                distinct_keys = exploded_df.select("key").distinct().collect()
                for row in distinct_keys:
                    key = row["key"]
                    key_df = exploded_df.filter(col("key") == key).select("value")
                    stats_dict[f"{full_field_name}~{key}"] = compute_stats(
                        key_df, "value", value_type, compute_all, full_field_name
                    )

                if isinstance(value_type, StructType):
                    stats_dict.update(
                        profile_data(
                            exploded_df.select("value.*"), new_depth, compute_all, full_field_name
                        )
                    )
                elif isinstance(value_type, MapType) or isinstance(value_type, ArrayType):
                    stats_dict.update(
                        profile_data(
                            exploded_df.select("value"), new_depth, compute_all, full_field_name
                        )
                    )

        elif isinstance(field_type, ArrayType):
            stats_dict[full_field_name] = compute_stats(
                df, field_name, field_type, compute_all, full_field_name
            )
            element_type = field_type.elementType
            exploded_df = df.select(explode(col(field_name)).alias("element"))

            # Compute stats for subfields
            if max_depth is None or max_depth > 0:
                new_depth = None if max_depth is None else max_depth - 1
                if isinstance(element_type, StructType):
                    stats_dict.update(
                        profile_data(
                            exploded_df.select("element.*"), new_depth, compute_all, full_field_name
                        )
                    )
                elif isinstance(element_type, MapType):
                    stats_dict.update(
                        profile_data(
                            exploded_df.select("element"), new_depth, compute_all, full_field_name
                        )
                    )

        else:
            # Compute stats for non-complex data types
            stats_dict[full_field_name] = compute_stats(
                df, field_name, field_type, compute_all, field_type
            )

    return stats_dict


def compute_stats(df, field_name, field_type, compute_all, parent=None):
    """Compute statistics for field.
        Statistics calculated:
            dtype: Data type of field
            totalcount: Total number of rows in dataset
            filledcount: Non-null count of field
            nullcount: Null count of field
            uniquevals: List of unique values in field
            nunique: Number of unique values in field
            maxlen: Maximum character length of values in field
            minlen: Minimum character length of values in field
            max: Maximum value of values in field (only applicabel to numeric type data)
            min: Minimum value of values in field (only applicabel to numeric type data)
            mean: Average length of values in field (only applicable to numeric type data)
            stddev: Standard deviation of values in field (only applicable to numeric type data)
            frequency: Frequency count of each unique value in field

    Params:
        df: Dataset containing the field
        field_name: Name of field
        field_type: Data type of field
         compute_all: Whther to compute all statistics. If True does full suite of statistics computation for each field. If False, only computes dtype, total count of rows, filled row counts, null row counts and sparsness of data for each field.
        parent: Parent field name

    Returns:
        Dictionary containing statistics for field
    """

    # Init empty dictionary
    stats_keys = [
        "dtype",
        "totalcount",
        "filledcount",
        "nullcount",
        "sparsness",
        "uniquevals",
        "nunique",
        "maxlen",
        "minlen",
        "max",
        "min",
        "mean",
        "stddev",
        "frequency",
    ]

    stats = {key: None for key in stats_keys}

    # Common statistics
    stats["dtype"] = (
        field_type.simpleString().split("<")[0]
        if "<" in field_type.simpleString()
        else field_type.simpleString()
    )
    stats["totalcount"] = df.count()
    stats["filledcount"] = df.agg(count(when(col(field_name).isNotNull(), field_name))).first()[0]
    stats["nullcount"] = stats["totalcount"] - stats["filledcount"]
    stats["sparsness"] = stats["nullcount"] / stats["totalcount"]

    if compute_all:
        if isinstance(field_type, StructType):
            # Struct Type data stats
            stats["uniquevals"] = [struct_field.name for struct_field in field_type.fields]
            stats["nunique"] = len(stats["uniquevals"])

            subfield_names = field_type.fieldNames()
            df_with_key_counts = df.withColumn(
                "key_count",
                reduce(
                    lambda a, b: a + b,
                    [
                        when(col(f"{field_name}.{subfield}").isNotNull(), 1).otherwise(0)
                        for subfield in subfield_names
                    ],
                ),
            )

            stats["maxlen"] = df_with_key_counts.agg(max(col("key_count"))).first()[0]
            stats["minlen"] = df_with_key_counts.agg(max(col("key_count"))).first()[0]

        elif isinstance(field_type, MapType):
            # Map Type data stats
            exploded_df = df.select(explode(field_name).alias("key", "value"))
            stats["uniquevals"] = [row[0] for row in exploded_df.select("key").distinct().collect()]
            stats["nunique"] = len(stats["uniquevals"])
            stats["maxlen"] = exploded_df.agg(min(length(col("key")))).first()[0]
            stats["minlen"] = exploded_df.agg(min(length(col("key")))).first()[0]

        elif isinstance(field_type, ArrayType):
            # Array Type data stats
            stats["uniquevals"] = [
                row[0] for row in df.select(explode(col(field_name))).distinct().collect()
            ]
            stats["nunique"] = len(stats["uniquevals"])
            stats["maxlen"] = df.agg(max(size(col(field_name)))).first()[0]
            stats["minlen"] = df.agg(min(size(col(field_name)))).first()[0]

        else:
            stats["uniquevals"] = [row[0] for row in df.select(field_name).distinct().collect()]
            stats["nunique"] = len(stats["uniquevals"])
            stats["maxlen"] = df.agg(max(length(col(field_name)))).first()[0]
            stats["minlen"] = df.agg(min(length(col(field_name)))).first()[0]

            if isinstance(field_type, TimestampType):
                # Frequency count for Timestamp type fields
                df_with_date = df.withColumn("date", to_date(df[field_name]))
                stats["frequency"] = {
                    str(row[field_name]): row["count"]
                    for row in df_with_date.groupBy(field_name).count().collect()
                }
            else:
                stats["frequency"] = {
                    str(row[field_name]): row["count"]
                    for row in df.groupBy(field_name).count().collect()
                }

            if isinstance(field_type, NumericType):
                # Numeric-specific stats
                stats["max"] = df.agg(max(col(field_name))).first()[0]
                stats["min"] = df.agg(min(col(field_name))).first()[0]
                stats["stddev"] = round(df.agg(stddev(col(field_name))).first()[0], 3)
                stats["mean"] = round(df.agg(avg(col(field_name))).first()[0], 3)

    return stats


def write_to_table(spark, data_dict, table_path=None):
    """Convert dictionary into a DLT.

    Params:
        data_dict: data source in dictionary format
        table_path: (Optional) Full path to save table to. Default None

    Returns:
        (Currently) Returns Spark table
        (alternative) Creates a table containing the data at table_path
    """
    # Flatten dictionary
    rows = []
    for key, stats in data_dict.items():
        row = [str(key)] + [
            stats.get(col, None)
            for col in [
                "dtype",
                "totalcount",
                "filledcount",
                "nullcount",
                "sparsness",
                "uniquevals",
                "nunique",
                "maxlen",
                "minlen",
                "max",
                "min",
                "mean",
                "stddev",
                "frequency",
            ]
        ]
        rows.append(row)

    # Define the schema
    schema = StructType(
        [
            StructField("fieldname", StringType(), True),
            StructField("dtype", StringType(), True),
            StructField("totalcount", LongType(), True),
            StructField("filledcount", LongType(), True),
            StructField("nullcount", DoubleType(), True),
            StructField("sparsness", FloatType(), True),
            StructField("uniquevals", ArrayType(StringType()), True),
            StructField("nunique", LongType(), True),
            StructField("maxlen", IntegerType(), True),
            StructField("minlen", IntegerType(), True),
            StructField("max", DoubleType(), True),
            StructField("min", DoubleType(), True),
            StructField("mean", DoubleType(), True),
            StructField("stddev", DoubleType(), True),
            StructField("frequency", MapType(StringType(), IntegerType()), True),
        ]
    )

    # Create table from statistics dictionary
    stats_df = spark.createDataFrame(rows, schema)

    # Add computed timestamp
    stats_df = stats_df.withColumn("_dts", lit(datetime.now()))

    if table_path:
        # Write to path
        return (
            stats_df.write.format("delta")
            .mode("append")
            .option("mergeSchema", "true")
            .saveAsTable(table_path)
        )
    else:
        # Return table (used for case of converting expected data values into table)
        return stats_df
