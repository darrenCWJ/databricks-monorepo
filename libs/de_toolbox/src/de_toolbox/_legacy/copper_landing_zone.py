import importlib.util
import json
import os
import re
from datetime import datetime

import pandas as pd
from databricks.sdk.runtime import *

from de_toolbox.catalog import get_catalog, get_repo_path
from de_toolbox.permissions import (
    change_securable_object_owner,
    grant_securable_object_permission_in_dev,
    set_securable_object_tag,
)


# Function to load a user defined transformation
def load_byot_from_repo(repo_path, transformation_file, function_name):
    """
    Load a user-defined transformation from a specific file in the repo,
    or use the default transformation if the file doesn't exist.

    :param repo_path: Path to the repository directory.
    :param transformation_file: Name of the transformation file to check for.
    :param function_name: Name of the function to load from the file.
    :return: The user-defined function if it exists, otherwise the default function.
    """
    file_path = os.path.join(repo_path, transformation_file)

    # Check if the transformation file exists in the repo
    if not os.path.isfile(file_path):
        print("Transformation file not found. Using default transformation.")
        return default_byot

    # Dynamically load the module if the file exists
    spec = importlib.util.spec_from_file_location("repo_module", file_path)
    repo_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(repo_module)

    # Get the transformation function from the module
    if hasattr(repo_module, function_name):
        return getattr(repo_module, function_name)
    else:
        raise AttributeError(f"Transformation file does not contain function '{function_name}'")


# Function to check the file type match the given path
def check_file_type(file_path, file_type):
    """
    Check if the given file path has the correct extension for the specified file type.

    :param file_path: The path to the file to be checked.
    :param file_type: The expected file type. Supported types are 'csv', 'excel', 'json', 'parquet', and 'avro'.
    :return: True if the file extension matches the specified file type, False otherwise
    """
    # Get the file extension
    _, extension = os.path.splitext(file_path)
    extension = extension.lower()

    # Convert file_type to lowercase for case-insensitive comparison
    file_type = file_type.lower()

    if file_type == "csv":
        return extension == ".csv"
    elif file_type == "excel":
        return extension in [".xls", ".xlsx", ".xlsm"]
    elif file_type == "json":
        return extension == ".json"
    elif file_type == "parquet":
        return extension == ".parquet"
    elif file_type == "avro":
        return extension == ".avro"
    else:
        return False


# Function to check naming convention with a given file name regex
def check_file_name_convention(file_path, file_name_regex):
    """
    Check if the file name in the given file path matches the specified regex pattern.

    Args:
        file_path (str): The path to the file to be checked.
        file_name_regex (str): A regular expression pattern that the file name should match.

    Returns:
        bool: True if the file name matches the regex pattern, False otherwise.

    Note:
        - The function extracts the file name from the path and checks it against the regex.
        - The regex pattern should match the entire file name (excluding the extension).
        - If the regex is invalid, the function will return False and print an error message.
    """
    # Extract the file name from the path
    file_name = os.path.basename(file_path)

    # Split the file name and extension
    name_without_extension, _ = os.path.splitext(file_name)

    try:
        # Check if the file name matches the regex pattern
        if re.match(file_name_regex, name_without_extension):
            return True
        else:
            return False
    except re.error as e:
        print(f"Error in regex pattern: {e}")
        return False


# The default transformation that would be use in byot
def default_byot(df):
    """
    Default transformation to apply if no custom transformation is found.
    In this example, it's a no-op (returns the original DataFrame).

    :param df: The DataFrame to transform.
    :return: The same DataFrame without any changes.
    """
    return df


# The function that would apply the byot transformation
def apply_byot(df, repo_path, transformation_file, function_name):
    """
    Apply either the custom transformation from the repository, or the default transformation.

    :param df: The DataFrame to transform.
    :param repo_path: Path to the repository where the transformation file might be.
    :param transformation_file: The filename of the transformation file in the repo.
    :param function_name: The function name to call from the transformation file.
    :return: Transformed DataFrame.
    """
    if not transformation_file or not function_name:
        transformation_func = default_byot
        print("Transformation file or function not given. Using default transformation.")
    else:
        transformation_func = load_byot_from_repo(repo_path, transformation_file, function_name)

    # Apply the transformation function to the DataFrame
    transformed_df = transformation_func(df)

    return transformed_df


# Function to check if columns in dataframe is same as known_columns
def check_columns(df, known_columns, whitelist=[]):
    """
    Check if columns in dataframe match known_columns, excluding whitelist columns.

    Args:
    df (pandas.DataFrame): The DataFrame to check.
    known_columns (list): The list of expected column names.
    whitelist (list): Columns to exclude from the comparison.

    Returns:
    bool: True if columns match (excluding whitelist), False otherwise.
    """
    # Remove whitelist columns from both df.columns and known_columns
    df_columns = [col for col in df.columns if col not in whitelist]
    filtered_known_columns = [col for col in known_columns if col not in whitelist]

    # Sort the filtered columns
    sorted_columns = sorted(df_columns)
    sorted_known_columns = sorted(filtered_known_columns)

    if sorted_columns == sorted_known_columns:
        print("Columns match (excluding whitelist)")
        return True
    else:
        print("Columns do NOT match (excluding whitelist)")
        print("Dataframe columns (excluding whitelist):")
        print(sorted_columns)
        print("Expected columns (excluding whitelist):")
        print(sorted_known_columns)
        return False


# Function to title and then clean column names
def clean_and_title_column_names(columns):
    """
    Clean and format column names by titling words, removing invalid characters,
    and replacing spaces with underscores.

    Args:
    columns (list): A list of column names to be cleaned.

    Returns:
    list: A list of cleaned and formatted column names.
    """
    # Title each word's first letter
    # This capitalizes the first letter of each word in the column names
    titled_columns = [col.title() for col in columns]

    # Remove invalid characters
    # This step removes any character that is not a letter, number, or space
    cleaned_columns = [re.sub(r"[^a-zA-Z0-9 ]", "", col) for col in titled_columns]

    # Remove extra spaces and replace spaces with underscores
    # This step removes any leading/trailing spaces and replaces remaining spaces with nothing
    final_columns = [re.sub(r"\s+", "", col).strip() for col in cleaned_columns]

    return final_columns


# Function to concatenate a dictionary of DataFrames
def concat_dict_dataframes(df_dict):
    """
    Concatenate all DataFrames stored as values in a dictionary into a single DataFrame.

    Args:
    df_dict (dict): A dictionary where values are pandas DataFrames.

    Returns:
    pandas.DataFrame: A single DataFrame containing all data from the input DataFrames.
    """
    # Get a list of all DataFrames in the dictionary
    # This extracts all the DataFrame objects stored as values in the input dictionary
    dataframes = list(df_dict.values())

    # Concatenate all DataFrames
    # pd.concat combines all DataFrames vertically (stacking them on top of each other)
    # ignore_index=True resets the index of the resulting DataFrame to avoid duplicate indices
    result = pd.concat(dataframes, ignore_index=True)

    return result


# Function to convert millisecond timestamp into given string format
def ms_to_formatted_date(timestamp_ms, format_string):
    """
    Convert a millisecond timestamp to a formatted date string.

    Args:
    timestamp_ms (int): The timestamp in milliseconds.
    format_string (str): The desired output format using strftime directives.

    Returns:
    str: The formatted date string.
    """
    # Convert milliseconds to seconds by dividing by 1000
    timestamp_seconds = timestamp_ms / 1000

    # Create a datetime object from the timestamp
    date_obj = datetime.fromtimestamp(timestamp_seconds)

    # Format the datetime object according to the specified format string
    return date_obj.strftime(format_string)


# Function to get all files from a given path
def get_all_files(path, files=None):
    """
    Recursively lists all files under the given path.

    :param path: The path to list files from.
    :param files: Used for recursive calls to accumulate files.
    :return: A list of all file paths under the given path.
    """
    if files is None:
        files = []

    items = dbutils.fs.ls(path)

    for item in items:
        if item.isDir():  # If the item is a directory, recursively call the function
            get_all_files(item.path, files)
        else:  # If the item is a file, add its path to the list
            files.append(item)

    return files


# Function to get a list of files from a given path
def list_all_files(path, files=None):
    """
    Recursively lists all files under the given path.

    :param path: The path to list files from.
    :param files: Used for recursive calls to accumulate files.
    :return: A list of all file paths under the given path.
    """
    if files is None:
        files = []

    items = dbutils.fs.ls(path)

    for item in items:
        if item.isDir():  # If the item is a directory, recursively call the function
            list_all_files(item.path, files)
        else:  # If the item is a file, add its path to the list
            files.append(item.path.replace("dbfs:", ""))

    return files


# Function to get a dict of files from a given path
def dict_all_files(path, files=None):
    """
    Recursively lists all files under the given path and stores them in a dictionary.

    :param path: The path to list files from.
    :param files: Used for recursive calls to accumulate files. Should be None on initial call.
    :return: A dictionary of all file paths under the given path, with the file paths as keys.
    """
    if files is None:
        files = {}

    items = dbutils.fs.ls(path)

    for item in items:
        if item.isDir():  # If the item is a directory, recursively call the function
            dict_all_files(item.path, files)
        else:  # If the item is a file, add its path to the dictionary
            files[item.path.replace("dbfs:", "")] = True  # Or any other value you deem appropriate

    return files


# Function to get a dict of files from a given path
def clear_all_files(path, files=None):
    """
    Recursively lists all files under the given path and stores them in a dictionary.

    :param path: The path to list files from.
    :param files: Used for recursive calls to accumulate files. Should be None on initial call.
    :return: A dictionary of all file paths under the given path, with the file paths as keys.
    """
    if files is None:
        files = {}

    items = dbutils.fs.ls(path)

    for item in items:
        if item.isDir():  # If the item is a directory, recursively call the function
            clear_all_files(item.path, files)
        else:  # If the item is a file, add its path to the dictionary
            dbutils.fs.rm(item.path.replace("dbfs:", ""), recurse=False)


# Function to get file path(s) from a specified volume
def get_files_from_volume(metadata, catalog):
    """
    Retrieve file path(s) from a specified volume based on the configuration.

    Args:
    metadata (dict): A dictionary containing configuration parameters.
        Expected keys:
        - 'volumn_ingestion_schema': The schema within the volume to search for files.
        - 'volumn_ingestion_path': The path within the volume to search for files.
        - 'volumn_ingestion_method': Either 'single' for the latest file or 'all' for all files.

    Returns:
    list: A list of file objects. For 'single' method, it contains only the latest file.
          For 'all' method, it contains all files sorted by modification time (newest first).

    Note: This function assumes the existence of a global CATALOG variable and dbutils object.
    """
    # Construct the full file path using the CATALOG and the specified ingestion path
    volumn_ingestion_schema = metadata.get("common", {}).get("volume_ingestion_schema", "bronze")
    volumn_ingestion_path = metadata.get("common", {}).get("volume_ingestion_path")
    file_path = f"/Volumes/{catalog}/{volumn_ingestion_schema}/{volumn_ingestion_path}/"

    # List all files in the specified volume path
    # dbutils.fs.ls is a Databricks utility function to list files
    files = get_all_files(file_path)

    # Sort the files by modification time in descending order (newest first)
    # Each file object is expected to have a 'modificationTime' attribute
    sorted_files = sorted(files, key=lambda file: file.modificationTime, reverse=True)

    # Check the ingestion method specified in the configuration
    if metadata.get("common", {}).get("volume_ingestion_method") == "single":
        # If 'single', return only the latest file (first in the sorted list)
        print(f"get_files_from_volume: 1 file at path: {file_path}")
        return sorted_files[:1]

    elif metadata.get("common", {}).get("volume_ingestion_method") == "all":
        # If 'all', return all files (entire sorted list)
        print(f"get_files_from_volume: {len(sorted_files)} file at path: {file_path}")
        return sorted_files


# Function to convert file path from source to target
def convert_path(source_file_path, source_base_path, target_base_path, initial_file_config):
    """
    Convert a source file path to a target file path, maintaining the directory structure
    and potentially changing the file extension.

    Args:
        source_file_path (str): The full path of the source file.
        source_base_path (str): The base path of the source files.
        target_base_path (str): The base path where files should be moved to.
        initial_file_config (dict): Configuration dictionary that may contain 'file_type'.

    Returns:
        str: The new path for the file in the target location, potentially with a new extension.

    Note:
        - This function assumes that source_file_path starts with source_base_path.
        - The directory structure after source_base_path will be maintained in the target path.
        - If initial_file_config['file_type'] is 'csv' or 'excel', the output file extension will be changed to '.parquet'.
    """
    # Ensure the paths don't end with a slash for consistent handling
    source_base_path = source_base_path.rstrip("/")
    target_base_path = target_base_path.rstrip("/")

    # Get the relative path of the file from the source base path
    relative_path = os.path.relpath(source_file_path, source_base_path)

    # Split the path and filename
    dir_path, filename = os.path.split(relative_path)

    # Check if we need to change the file extension
    if initial_file_config.get("file_type") in ["csv", "excel"]:
        # Split the filename and extension
        name, _ = os.path.splitext(filename)
        # Create new filename with .parquet extension
        filename = f"{name}.parquet"

    # Construct the new path by joining the target base path, directory path, and potentially modified filename
    new_path = os.path.join(target_base_path, dir_path, filename)

    return new_path


def copy_files_from_s3_to_volume(initial_file_config, catalog):
    """
    Copy or move files from S3 to a managed volume, preserving folder structure.

    Args:
    initial_file_config (dict): Configuration containing S3 and volume parameters.
        Expected keys:
        - 's3_path': The full S3 path (e.g., "s3://bucket-name/folder/")
        - 'target_schema': Target schema for the managed volume
        - 'target_volume': Target volume name
        - 's3_transfer_method': Either 'copy' or 'move' (default: 'copy')

    Returns:
    bool: True if transfer successful, False otherwise
    """
    # Get configuration parameters
    s3_path = initial_file_config.get("s3_path")
    target_schema = initial_file_config.get("target_schema", "bronze")
    target_volume = initial_file_config.get("target_volume")
    transfer_method = initial_file_config.get("s3_transfer_method", "copy")
    retention_days = initial_file_config.get("retention_days", 60)

    if not all([s3_path, target_schema, target_volume]):
        print("Missing required S3 or target volume configuration")
        return False

    # Ensure S3 path ends with /
    if not s3_path.endswith("/"):
        s3_path += "/"

    # Construct target volume path
    target_volume_path = f"/Volumes/{catalog}/{target_schema}/{target_volume}/"

    try:
        # Create schema and volume if they don't exist
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{target_schema}")
        spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{target_schema}.{target_volume}")

        # Get all files from S3
        s3_files = get_all_files(s3_path)

        if not s3_files:
            print(f"No files found in S3 path: {s3_path}")
            return False

        # Transfer each file from S3 to volume
        transferred_count = 0
        for s3_file in s3_files:
            try:
                # Calculate relative path from the base S3 path
                relative_path = s3_file.path.replace(s3_path, "")

                # Construct target file path preserving folder structure
                target_file_path = f"{target_volume_path}{relative_path}"

                # # Create target directory if it doesn't exist
                # target_dir = "/".join(target_file_path.split("/")[:-1]) + "/"
                # try:
                #     dbutils.fs.mkdirs(target_dir)
                # except:
                #     # Directory might already exist, continue
                #     pass

                if transfer_method == "move":
                    # Move file using dbutils
                    dbutils.fs.mv(s3_file.path, target_file_path)
                    print(f"Moved: {s3_file.path} -> {target_file_path}")
                else:
                    # Copy file using dbutils (default)
                    dbutils.fs.cp(s3_file.path, target_file_path)
                    print(f"Copied: {s3_file.path} -> {target_file_path}")

                transferred_count += 1

            except Exception as e:
                print(f"Error transferring {s3_file.path}: {e}")

        print(f"Successfully {transfer_method}d {transferred_count} files from S3 to volume")
        return transferred_count > 0

    except Exception as e:
        print(f"Error during S3 to volume {transfer_method} operation: {e}")
        return False


def validate_landing_zone_config(landing_zone_config):
    """
    Validate the landing zone configuration for S3 sources.

    Args:
    landing_zone_config (dict): Landing zone configuration to validate

    Returns:
    tuple: (is_valid: bool, error_messages: list)
    """
    errors = []

    if not isinstance(landing_zone_config, dict):
        errors.append("landing_zone must be a dictionary")
        return False, errors

    # Required fields
    required_fields = ["s3_path", "target_schema", "target_volume"]
    for field in required_fields:
        if not landing_zone_config.get(field):
            errors.append(f"Missing required field: {field}")

    # Validate s3_path format
    s3_path = landing_zone_config.get("s3_path")
    if s3_path and not s3_path.startswith("s3://"):
        errors.append("s3_path must start with 's3://'")

    # Validate s3_transfer_method
    transfer_method = landing_zone_config.get("s3_transfer_method", None)
    valid_methods = ["copy", "move"]
    if transfer_method not in valid_methods:
        errors.append(f"s3_transfer_method must be one of: {valid_methods}")

    # Validate target_schema and target_volume naming
    target_schema = landing_zone_config.get("target_schema")
    if target_schema and not target_schema.replace("_", "").isalnum():
        errors.append("target_schema must contain only alphanumeric characters and underscores")

    target_volume = landing_zone_config.get("target_volume")
    if target_volume and not target_volume.replace("_", "").isalnum():
        errors.append("target_volume must contain only alphanumeric characters and underscores")

    return len(errors) == 0, errors


def save_pandas_df_to_volume(df_dict, files_dict_exist, volume_path, dict_key):
    target_path = f"{volume_path}/{dict_key}.parquet"
    if target_path in files_dict_exist.keys():
        print(f"Copy skipped {target_path} exists")
    else:
        df_dict.get(dict_key).to_parquet(f"{volume_path}/{dict_key}.parquet", index=False)
        print(f"Files saved to {target_path}")


def process_file_type_validation(metadata, volume_file):

    file_type = metadata.get("common", {}).get("file_type", None).lower()

    # Processing each_file in the volume_file
    for each_file in volume_file:
        print(f"Processing file_type_validation: {each_file.name}")
        if check_file_type(each_file.name, file_type):
            pass
        else:
            print(f"File {each_file.name}, does not meet expected {file_type}, pipeline terminate")
            return False

    return True


def process_file_naming_validation(metadata, volume_file):

    file_name_regex = metadata.get("validation_setting", {}).get("file_name_regex", None)

    # Processing each_file in the volume_file
    for each_file in volume_file:
        print(f"Processing file_naming_validation: {each_file.name}")
        # File Metadata Validation - File Naming Convention
        if check_file_name_convention(each_file.name, file_name_regex):
            pass
        else:
            print(f"Skipped file {each_file.name}, file name regex failed validation")
            return False

    return True


def process_schema_validation(metadata, volume_file):

    file_type = metadata.get("common", {}).get("file_type", None).lower()
    schemas_list = metadata.get("validation_setting", {}).get("schema", [])

    if not file_type:
        print("File type not found in metadata, cannot process schema validation")
        return False
    # Only excel file type can have multiple schema in a single file
    elif file_type != "excel" and len(schemas_list) > 1:
        print(
            f"File type {file_type} is not supported for multiple schema validation @  [{len(schemas_list)}] schemas"
        )
        return False

    # Processing each_file in the volume_file
    for each_file in volume_file:
        print(f"Processing schema_validation: {each_file.name}")

        for each_schema in schemas_list:
            print(f"Processing schema_validation for schema: {each_schema['output_suffix']}")
            # Performing Schema Validation Check
            known_columns = each_schema["known_columns"]
            kwargs = each_schema["kwargs"]

            if file_type == "excel":
                df = pd.read_excel(each_file.path.replace("dbfs:", ""), **kwargs)
            elif file_type == "csv":
                df = pd.read_csv(each_file.path.replace("dbfs:", ""), **kwargs)
            elif file_type == "json":
                df = pd.read_json(each_file.path.replace("dbfs:", ""), **kwargs)
            elif file_type == "parquet":
                df = pd.read_parquet(each_file.path.replace("dbfs:", ""), **kwargs)

            # Check if the DataFrame columns match the known columns
            check_result = check_columns(
                df, known_columns, ["CDOFileIngestTimestamp", "CDOFileVolumeTimestamp"]
            )

            if not check_result:
                print("Expected Columns does not match actual file columns")
                return False

    return True


def extract_file_content(metadata, volume_file, current_timestamp, current_timestamp_file):

    schemas_list = metadata.get("validation_setting", {}).get("schema", [])

    # Read each datasets within the given metadata schemas_list
    for each_schema in schemas_list:
        print(f"Processing sheet {each_schema['output_suffix']}")
        # Output Dict of Pandas Dataframe
        df_result = {}

        # Processing each_file in the volume_file
        for each_file in volume_file:
            print(f"Processing file {each_file.name}")

            # Performing Schema Validation Check
            known_columns = each_schema["known_columns"]
            kwargs = each_schema["kwargs"]

            if metadata.get("file_type") == "excel":
                df = pd.read_excel(each_file.path.replace("dbfs:", ""), **kwargs)

            # Clean and title column names
            df.columns = clean_and_title_column_names(df.columns)

            # Add the Current Runtime Timestamp column as CDOFileIngestTimestamp
            df["CDOFileIngestTimestamp"] = current_timestamp

            # Add the modificationTime of the original file as CDOFileVolumeTimestamp
            df["CDOFileVolumeTimestamp"] = ms_to_formatted_date(
                each_file.modificationTime, "%Y-%m-%dT%H:%M:%S"
            )

            # Fill NA
            df = df.fillna("")

            # Retrive the file_name
            file_name = each_file.path.split("/")[-1].split(".")[0].lower()

            # Implement byot transformation
            byot_setting = sheet_info.get("byot", None)
            if not byot_setting:
                byot_file = None
                byot_function = None
            else:
                byot_file = byot_setting.get("file_name", None)
                byot_function = byot_setting.get("function_name", None)
            df = apply_byot(df, "../byot", byot_file, byot_function)

            # Adding dataframe to dict
            df_result[file_name] = df

        # Saving list of dataframe to table or volume
        # Please take note, if saving to volume output_suffix would only apply to volume name, and for each files the original naming would be used instead, so please ensure naming convention is properly followed
        if each_schema["output_type"] == "volume":
            output_suffix = each_schema.get("output_suffix")
            output_schema = each_schema.get("output_schema", "bronze")
            volume_target_path = f"/Volumes/{catalog}/{output_schema}/{output_suffix}"

            if reload_copper:
                clear_all_files(volume_target_path)

            try:
                spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
                spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{output_schema}")
                spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{output_schema}.{output_suffix}")
                # Assign tag
                set_securable_object_tag(
                    spark, metadata, sheet_info, f"{catalog}.{output_schema}.{output_suffix}"
                )
            except:
                print("Catalog, Schema, Volume Creation Error")

            if not reload_copper:
                FILES_DICT_EXIST = dict_all_files(volume_target_path)
            else:
                FILES_DICT_EXIST = {}

            for each_dict in df_result:
                save_pandas_df_to_volume(df_result, FILES_DICT_EXIST, volume_target_path, each_dict)

        elif each_schema["output_type"] == "table":
            output_suffix = each_schema.get("output_suffix")
            output_schema = each_schema.get("output_schema", "bronze")

            try:
                spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
                spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{output_schema}")
            except:
                print("Catalog, Schema, Creation Error")

            # Concat all dataframe in dict
            df = concat_dict_dataframes(df_result)

            # Convert pandas DataFrame to Spark DataFrame
            spark_df = spark.createDataFrame(df)

            # Write the data to the table
            spark_df.write.option("overwriteSchema", "True").mode("overwrite").saveAsTable(
                f"{catalog}.{output_schema}.{output_suffix}"
            )
            print(f"Table saved to {catalog}.{output_schema}.{output_suffix}")

            # Assign tag
            set_securable_object_tag(
                spark, metadata, sheet_info, f"{catalog}.{output_schema}.{output_suffix}"
            )

            # Change owner
            change_securable_object_owner(
                spark,
                metadata,
                sheet_info,
                catalog.split("_")[0],
                catalog.split("_")[-1],
                f"{catalog}.{output_schema}.{output_suffix}",
            )

            # Change permission
            grant_securable_object_permission_in_dev(
                spark,
                metadata,
                catalog.split("_")[0],
                catalog.split("_")[-1],
                f"{catalog}.{output_schema}.{output_suffix}",
            )

    return pipeline_progress


# Function to create the parquet file or save direct to bronze
def run_initial_task(spark, metadata, catalog, reload_copper):
    # Feature of Function
    # Move File From Target External Volume to Managed Volume
    # Check File Checksum before and after copy
    # Store Metadata about files in a delta table such as original file modifiy and create time, source and target path
    # Perform File Type Check
    # Perform File Name Check
    # Perform Schema Check

    # Processing S3 to Volume Script
    landing_zone_config = metadata.get("landing_zone", {})

    if landing_zone_config:
        print("S3 source detected - validating configuration...")

        # Validate landing zone configuration
        is_valid, validation_errors = validate_landing_zone_config(landing_zone_config)

        if not is_valid:
            print("Landing zone configuration validation failed:")
            for error in validation_errors:
                print(f"  - {error}")
            return False

        print("Configuration validation passed. Processing files in s3 path...")

        # Copy files from S3 to managed volume
        copy_success = copy_files_from_s3_to_volume(landing_zone_config, catalog)

        if not copy_success:
            print("Failed to copy files from S3 to volume")
            return False

        print("Files copied successfully. Proceeding with volume-based processing...")

    # Load up the list of file needed to be process
    volume_file = get_files_from_volume(metadata, catalog)

    # Setting the workflow parameter
    pipeline_progress = True

    # Display the volume file
    if volume_file:
        print(f"Number of file: {len(volume_file)}")
    else:
        # Change pipeline_progress to False
        pipeline_progress = False
        # Print out reason
        print("No files found in given path.")
        # Return the function
        return pipeline_progress

    validation_config = metadata.get("validation", {})
    validation_setting = metadata.get("validation_setting", {})
    file_type_validation = validation_config.get("file_type", False)
    file_naming_validation = validation_config.get("file_naming", False)
    schema_validation = validation_config.get("schema", False)

    if file_type_validation:
        pipeline_progress = process_file_type_validation(metadata, volume_file)
        if not pipeline_progress:
            return False

    if file_naming_validation:
        pipeline_progress = process_file_naming_validation(metadata, volume_file)
        if not pipeline_progress:
            return False

    if schema_validation:
        pipeline_progress = process_schema_validation(metadata, volume_file)
        if not pipeline_progress:
            return False

    cur_file_type = metadata.get("common", {}).get("file_type", None).lower()

    if cur_file_type == "excel" and schema_validation:
        # Generate the current timestamp in the specified format
        current_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        current_timestamp_file = datetime.now().strftime("%Y%m%d")

        pipeline_progress = extract_file_content(
            metadata, volume_file, current_timestamp, current_timestamp_file
        )
        if not pipeline_progress:
            return False


def create_copper(
    _spark, project, metadata_name, env, reload_copper, clear_copper=False, debug=None
):
    global spark
    if project == "toolbox":
        catalog = get_catalog("test", env)
    else:
        catalog = get_catalog(project, env)

    base_path = get_repo_path(project, debug, "copper")
    metadata_path = f"{base_path}/{metadata_name}.json"

    with open(metadata_path) as read_file:
        metadata = json.load(read_file)

    spark = _spark

    # Convert param to True/False
    reload_copper = spark.sql(f"select '{reload_copper}' is true").collect()[0][0]

    # Run the pipeline
    pipeline_progress = run_initial_task(spark, metadata, catalog, reload_copper)

    # Set the jobs taskValues for use in the workflow
    if pipeline_progress == True:
        dbutils.jobs.taskValues.set(key="pipeline_progress", value=True)
    else:
        dbutils.jobs.taskValues.set(key="pipeline_progress", value=False)
