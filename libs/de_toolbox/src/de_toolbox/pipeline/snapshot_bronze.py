import pyspark.sql.functions as F
from pyspark.sql import DataFrame


def process_bronze_to_mart_snapshot(
    spark, catalog: str, table_name: str, save_mode: bool = True, output_table_name: str = None
) -> DataFrame:
    """
    Reads a bronze table, filters by maximum _LOAD_DTS, and optionally saves to mart as snapshot.

    Args:
        spark (SparkSession): spark session
        catalog (str): The catalog name
        table_name (str): The bronze table name (without bronze prefix)
        save_mode (bool): True to save to table, False to skip saving (default: True)
        output_table_name (str): Custom output table name (will be prefixed with 'snapshot_').
                                If None, uses table_name (default: None)

    Returns:
        DataFrame: The filtered dataframe with max _LOAD_DTS
    """

    # Construct table paths
    bronze_table_path = f"{catalog}.bronze.{table_name}"

    # Determine output table name
    if output_table_name is None:
        final_output_name = table_name
    else:
        final_output_name = output_table_name

    mart_table_path = f"{catalog}.mart.snapshot_{final_output_name}"

    # Read the bronze table
    try:
        print(f"Reading bronze table: {bronze_table_path}")
        bronze_df = spark.table(bronze_table_path)
        print(f"Successfully read bronze table with {bronze_df.count()} total records")
    except Exception as e:
        print(f"Error reading bronze table {bronze_table_path}: {str(e)}")
        raise

    # Get the maximum _LOAD_DTS value
    try:
        max_load_dts = bronze_df.select(F.max("_LOAD_DTS")).collect()[0][0]
        print(f"Maximum _LOAD_DTS found: {max_load_dts}")
    except Exception as e:
        print(f"Error finding maximum _LOAD_DTS: {str(e)}")
        raise

    # Filter the dataframe by maximum _LOAD_DTS
    try:
        filtered_df = bronze_df.filter(bronze_df._LOAD_DTS == max_load_dts)
        record_count = filtered_df.count()
        print(f"Records with max _LOAD_DTS: {record_count}")
    except Exception as e:
        print(f"Error filtering dataframe by _LOAD_DTS: {str(e)}")
        raise

    # Save to mart layer if save_mode is True
    if save_mode:
        try:
            print(f"Saving to mart table: {mart_table_path}")
            filtered_df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
                mart_table_path
            )
            print(f"Successfully saved {record_count} records to {mart_table_path}")
        except Exception as e:
            print(f"Error saving to mart table {mart_table_path}: {str(e)}")
            raise
    else:
        print("Save mode is False - skipping save to mart table")

    print(f"Successfully processed {table_name}")
    return filtered_df
