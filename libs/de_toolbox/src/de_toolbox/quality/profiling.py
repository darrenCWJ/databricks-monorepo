"""Data profiling — compute column-level statistics for any DataFrame.

Supports nested types (struct, map, array) with configurable recursion depth.
"""

from datetime import datetime

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    avg,
    col,
    count,
    explode,
    length,
    lit,
    max,
    min,
    stddev,
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
)


def profile_data(df, max_depth: int = 0, compute_all: bool = False, parent=None) -> dict:
    """Compute statistics for each column in a DataFrame.

    Args:
        df: Input DataFrame.
        max_depth: Recursion depth for nested fields (0=top-level only).
        compute_all: If True, compute full stats including unique values.
        parent: Internal — parent field name for recursive calls.

    Returns:
        Dict mapping field names to their statistics dicts.
    """
    stats_dict = {}

    for field in df.schema.fields:
        full_name = f"{parent}~{field.name}" if parent else field.name
        field_type = field.dataType

        if isinstance(field_type, StructType):
            stats_dict[full_name] = _compute_stats(df, field.name, field_type, compute_all)
            if max_depth is None or max_depth > 0:
                nested_df = df.select(col(field.name + ".*"))
                new_depth = None if max_depth is None else max_depth - 1
                stats_dict.update(profile_data(nested_df, new_depth, compute_all, full_name))
        elif isinstance(field_type, ArrayType):
            stats_dict[full_name] = _compute_stats(df, field.name, field_type, compute_all)
            if max_depth is None or max_depth > 0:
                new_depth = None if max_depth is None else max_depth - 1
                if isinstance(field_type.elementType, StructType):
                    exploded = df.select(explode(col(field.name)).alias("element"))
                    stats_dict.update(
                        profile_data(
                            exploded.select("element.*"),
                            new_depth,
                            compute_all,
                            full_name,
                        )
                    )
        elif isinstance(field_type, MapType):
            stats_dict[full_name] = _compute_stats(df, field.name, field_type, compute_all)
        else:
            stats_dict[full_name] = _compute_stats(df, field.name, field_type, compute_all)

    return stats_dict


def write_to_table(spark: SparkSession, data_dict: dict, table_path: str | None = None):
    """Convert profiling stats to DataFrame and optionally save.

    Args:
        spark: Active SparkSession.
        data_dict: Output from profile_data().
        table_path: If provided, appends to this Delta table.

    Returns:
        DataFrame if table_path is None, otherwise writes to table.
    """
    stat_keys = [
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

    rows = [[str(key)] + [stats.get(k) for k in stat_keys] for key, stats in data_dict.items()]

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

    stats_df = spark.createDataFrame(rows, schema)
    stats_df = stats_df.withColumn("_dts", lit(datetime.now()))

    if table_path:
        return (
            stats_df.write.format("delta")
            .mode("append")
            .option("mergeSchema", "true")
            .saveAsTable(table_path)
        )
    return stats_df


def _compute_stats(df, field_name, field_type, compute_all):
    """Compute statistics for a single field."""
    total = df.count()
    filled = df.agg(count(when(col(field_name).isNotNull(), field_name))).first()[0]
    null_count = total - filled

    stats = {
        "dtype": field_type.simpleString().split("<")[0]
        if "<" in field_type.simpleString()
        else field_type.simpleString(),
        "totalcount": total,
        "filledcount": filled,
        "nullcount": null_count,
        "sparsness": null_count / total if total > 0 else 0,
    }

    if compute_all and not isinstance(field_type, (StructType, MapType, ArrayType)):
        stats["uniquevals"] = [row[0] for row in df.select(field_name).distinct().collect()]
        stats["nunique"] = len(stats["uniquevals"])
        stats["maxlen"] = df.agg(max(length(col(field_name)))).first()[0]
        stats["minlen"] = df.agg(min(length(col(field_name)))).first()[0]

        if isinstance(field_type, NumericType):
            stats["max"] = df.agg(max(col(field_name))).first()[0]
            stats["min"] = df.agg(min(col(field_name))).first()[0]
            stats["stddev"] = df.agg(stddev(col(field_name))).first()[0]
            stats["mean"] = df.agg(avg(col(field_name))).first()[0]

    return stats
