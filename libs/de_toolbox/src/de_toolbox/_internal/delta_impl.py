"""Internal implementation of save_df_to_delta_with_column_mapping.

Do not import directly — use de_toolbox.delta instead.
Verbatim port from de_toolbox/common/functions.py with only the function
name prefixed with underscore for internal use.
"""

import json
import traceback

from pyspark.sql import functions as F


def _save_df_to_delta_with_column_mapping(
    spark,
    df,
    table_path,
    save_data=True,
    save_mode="append",
    merge_keys=None,
    merge_condition=None,
    migrate_legacy=False,
    migrate_legacy_mode="temp_table",
    validate=None,
):
    """
    Clean DataFrame columns for Parquet compatibility and optionally save to Delta table
    with column mapping enabled using 'id' mode

    Args:
        spark: SparkSession
        df: DataFrame to save
        table_path: Full table path (e.g., "test_dev.default.my_table")
        save_data: Boolean, whether to save data to table (default: True)
        save_mode: String, "append", "merge", or "overwrite" (default: "append")
        merge_keys: List of ORIGINAL column names (before cleaning) to use as primary keys for merge
        merge_condition: Custom merge condition string using CLEANED column names (optional, overrides merge_keys if provided)
        migrate_legacy: Boolean, whether to migrate legacy tables without column mapping (default: False)
        migrate_legacy_mode: String, "cache" or "temp_table" - how to backup data during migration (default: "cache")
        validate: Dict, optional validation configuration with keys: "null", "distinct", "distinct_count", "column_name" (default: None)
                Example: {
                    "null": {"column1": [[0, 10], None], "column2": [[0, 5], "status = 'active'"]},
                    "distinct": {"col1,col2": None, "col3": None},
                    "distinct_count": {"col1,col2": [100, 1000], "col3": [50, 200]},
                    "column_name": ["col1", "col2", "col3"]
                }

    Returns:
        tuple: (cleaned_df, column_mapping_dict)
    """

    def validate_dataframe(df, validation_config):
        """
        Validate DataFrame based on configuration dictionary

        Args:
            df: DataFrame to validate
            validation_config: Dict with validation rules
                - "null": Dict of column -> [[min_count, max_count], filter_condition]
                - "distinct": Dict of "col1,col2" -> None (columns that should be distinct)
                - "distinct_count": Dict of "col1,col2" -> [min_count, max_count] (distinct count validation)
                - "column_name": List of expected column names

        Raises:
            AssertionError: If any validation fails
        """
        if not validation_config:
            print("ℹ️  No validation configuration provided, skipping validation")
            return

        print("🔍 Starting DataFrame validation...")

        # Validate column names
        if "column_name" in validation_config:
            expected_columns = set(validation_config["column_name"])
            actual_columns = set(df.columns)

            if actual_columns != expected_columns:
                missing_cols = expected_columns - actual_columns
                extra_cols = actual_columns - expected_columns
                error_msg = "Column Name Mismatch!\n"
                if missing_cols:
                    error_msg += f"Missing columns: {list(missing_cols)}\n"
                if extra_cols:
                    error_msg += f"Extra columns: {list(extra_cols)}"
                raise AssertionError(error_msg)

            print(
                f"✅ Column name validation passed - {len(actual_columns)} columns match expected"
            )

        # Validate null counts
        if "null" in validation_config:
            null_config = validation_config["null"]
            print(f"🔍 Validating null counts for {len(null_config)} columns...")

            for column_name, config in null_config.items():
                if column_name not in df.columns:
                    raise AssertionError(
                        f"Column '{column_name}' not found in DataFrame for null validation"
                    )

                threshold_range, filter_condition = config
                min_count, max_count = threshold_range

                # Increment max_count by 1 (matching original logic)
                max_count += 1

                # Apply filter condition if provided
                if filter_condition:
                    filtered_df = df.filter(filter_condition)
                    null_count = filtered_df.filter(F.col(column_name).isNull()).count()
                    print(
                        f"  📊 Column '{column_name}' (filtered by '{filter_condition}'): {null_count} null values"
                    )
                else:
                    null_count = df.filter(F.col(column_name).isNull()).count()
                    print(f"  📊 Column '{column_name}': {null_count} null values")

                # Check if null count is within acceptable range
                if null_count not in range(min_count, max_count):
                    raise AssertionError(
                        f"Column '{column_name}' null count [{null_count}] exceeds threshold range [{min_count}, {max_count - 1}]!"
                    )

            print(f"✅ Null count validation passed for all {len(null_config)} columns")

        # Validate distinct combinations (must be 100% distinct)
        if "distinct" in validation_config:
            distinct_config = validation_config["distinct"]
            print(
                f"🔍 Validating distinct combinations for {len(distinct_config)} column groups..."
            )

            for column_group, _ in distinct_config.items():
                # Parse column names (handle comma-separated values)
                columns = [col_name.strip() for col_name in column_group.split(",")]

                # Validate all columns exist
                missing_cols = [col_name for col_name in columns if col_name not in df.columns]
                if missing_cols:
                    raise AssertionError(
                        f"Columns {missing_cols} not found in DataFrame for distinct validation"
                    )

                # Check distinctness
                total_rows = df.count()
                distinct_rows = df.select(*columns).distinct().count()

                print(
                    f"  📊 Column group {columns}: {distinct_rows} distinct combinations out of {total_rows} total rows"
                )

                if distinct_rows != total_rows:
                    raise AssertionError(
                        f"Column group {columns} is not distinct! {distinct_rows} distinct vs {total_rows} total rows"
                    )

            print(f"✅ Distinct validation passed for all {len(distinct_config)} column groups")

        # Validate distinct count ranges
        if "distinct_count" in validation_config:
            distinct_count_config = validation_config["distinct_count"]
            print(
                f"🔍 Validating distinct count ranges for {len(distinct_count_config)} column groups..."
            )

            for column_group, count_range in distinct_count_config.items():
                # Parse column names (handle comma-separated values)
                columns = [col_name.strip() for col_name in column_group.split(",")]

                # Validate all columns exist
                missing_cols = [col_name for col_name in columns if col_name not in df.columns]
                if missing_cols:
                    raise AssertionError(
                        f"Columns {missing_cols} not found in DataFrame for distinct count validation"
                    )

                # Get distinct count
                distinct_count = df.select(*columns).distinct().count()

                # Validate count range
                min_count, max_count = count_range
                # Increment max_count by 1 to match range logic (consistent with null validation)
                max_count += 1

                print(f"  📊 Column group {columns}: {distinct_count} distinct combinations")
                print(f"      Expected range: [{min_count}, {max_count - 1}]")

                # Check if distinct count is within acceptable range
                if distinct_count not in range(min_count, max_count):
                    raise AssertionError(
                        f"Column group {columns} distinct count [{distinct_count}] exceeds threshold range [{min_count}, {max_count - 1}]!"
                    )

            print(
                f"✅ Distinct count validation passed for all {len(distinct_count_config)} column groups"
            )

        print("✅ All DataFrame validations passed successfully!")

    def clean_columns_for_parquet(df):
        """
        Minimal column cleaning for Parquet compatibility only
        Delta column mapping with 'id' mode supports: ,;{}()\n\t=. and spaces
        Only clean what Parquet cannot handle
        """
        original_columns = df.columns
        column_mapping = {}

        cleaned_columns = []
        for original_col in original_columns:
            # Only replace characters that Parquet cannot handle
            # Parquet doesn't support: leading/trailing spaces in some cases
            cleaned_col = original_col.strip()

            # Handle empty column names
            if not cleaned_col:
                cleaned_col = "unnamed_column"

            # Handle duplicates by adding suffix
            base_cleaned = cleaned_col
            counter = 1
            while cleaned_col in cleaned_columns:
                cleaned_col = f"{base_cleaned}_{counter}"
                counter += 1

            cleaned_columns.append(cleaned_col)

            # Only create mapping if names are different
            if cleaned_col != original_col:
                column_mapping[cleaned_col] = original_col

        # Rename columns in DataFrame
        df_renamed = df.toDF(*cleaned_columns)

        return df_renamed, column_mapping

    def check_table_exists_and_column_mapping(spark, table_path):
        """
        Check if table exists and validate column mapping configuration

        Returns:
            tuple: (table_exists: bool, column_mapping_enabled: bool, error_message: str)
        """
        try:
            # Check if table exists
            table_exists = spark.catalog.tableExists(table_path)

            if not table_exists:
                return False, False, None

            # Table exists, check column mapping configuration
            try:
                # Get table properties
                describe_result = spark.sql(f"DESCRIBE DETAIL {table_path}").collect()

                if not describe_result:
                    return True, False, f"Could not retrieve table details for {table_path}"

                # Extract properties from the result
                properties = (
                    describe_result[0].properties
                    if hasattr(describe_result[0], "properties")
                    else {}
                )

                # Check if properties is a string (JSON) and parse it
                if isinstance(properties, str):
                    try:
                        properties = json.loads(properties)
                    except json.JSONDecodeError:
                        properties = {}

                # Check column mapping mode
                column_mapping_mode = properties.get("delta.columnMapping.mode", None)

                print(f"Table {table_path} exists")
                print(f"Table properties: {properties}")
                print(f"Column mapping mode: {column_mapping_mode}")

                if column_mapping_mode == "id":
                    return True, True, None
                elif column_mapping_mode is None:
                    return (
                        True,
                        False,
                        f"Table {table_path} exists but column mapping is not enabled. Expected 'delta.columnMapping.mode' = 'id'",
                    )
                else:
                    return (
                        True,
                        False,
                        f"Table {table_path} exists but column mapping mode is '{column_mapping_mode}'. Expected 'id'",
                    )

            except Exception:
                # Try alternative method using SHOW TBLPROPERTIES
                try:
                    print(f"DESCRIBE DETAIL failed, trying SHOW TBLPROPERTIES for {table_path}")
                    properties_result = spark.sql(f"SHOW TBLPROPERTIES {table_path}").collect()

                    # Convert to dictionary
                    properties_dict = {}
                    for row in properties_result:
                        if hasattr(row, "key") and hasattr(row, "value"):
                            properties_dict[row.key] = row.value

                    print(f"Table properties from SHOW TBLPROPERTIES: {properties_dict}")

                    column_mapping_mode = properties_dict.get("delta.columnMapping.mode", None)
                    print(f"Column mapping mode: {column_mapping_mode}")

                    if column_mapping_mode == "id":
                        return True, True, None
                    elif column_mapping_mode is None:
                        return (
                            True,
                            False,
                            f"Table {table_path} exists but column mapping is not enabled. Expected 'delta.columnMapping.mode' = 'id'",
                        )
                    else:
                        return (
                            True,
                            False,
                            f"Table {table_path} exists but column mapping mode is '{column_mapping_mode}'. Expected 'id'",
                        )

                except Exception as e2:
                    return (
                        True,
                        False,
                        f"Table {table_path} exists but could not check column mapping properties. Error: {str(e2)}",
                    )

        except Exception as e:
            # Error checking table existence
            return False, False, f"Error checking table existence: {str(e)}"

    def backup_table_permissions(spark, table_path):
        """
        Backup Unity Catalog permissions for a table

        Args:
            spark: SparkSession
            table_path: Full table path (e.g., "cybsec_stg.vulnerability.bronze_codescape_systems")

        Returns:
            list: List of permission dictionaries for direct table permissions only
        """
        try:
            print(f"🔒 Backing up permissions for table: {table_path}")

            # Get table permissions using SHOW GRANTS
            grants_sql = f"SHOW GRANTS ON TABLE {table_path}"
            print(f"Executing: {grants_sql}")

            grants_result = spark.sql(grants_sql).collect()

            permissions = []
            for row in grants_result:
                # Extract permission details using the correct column names
                permission = {
                    "principal": getattr(row, "Principal", None),
                    "action_type": getattr(row, "ActionType", None),
                    "object_type": getattr(row, "ObjectType", None),
                    "object_key": getattr(row, "ObjectKey", None),
                }

                # Only include direct table permissions
                # Direct table permissions have ObjectType = 'TABLE' and ObjectKey = table_path
                if permission["object_type"] == "TABLE" and permission["object_key"] == table_path:
                    permissions.append(permission)
                    print(
                        f"  📋 Direct table permission: {permission['principal']} -> {permission['action_type']}"
                    )
                else:
                    # This is an inherited permission from catalog or schema level
                    print(
                        f"  ⏭️  Skipping inherited permission: {permission['principal']} -> {permission['action_type']} on {permission['object_type']} {permission['object_key']}"
                    )

            print(f"✓ Found {len(permissions)} direct table permissions to backup")
            return permissions

        except Exception as e:
            print(f"⚠️  Warning: Could not backup table permissions: {str(e)}")
            print(
                "This might be due to insufficient privileges or the table not having explicit permissions"
            )
            return []

    def restore_table_permissions(spark, table_path, permissions):
        """
        Restore Unity Catalog permissions for a table

        Args:
            spark: SparkSession
            table_path: Full table path
            permissions: List of permission dictionaries from backup_table_permissions

        Returns:
            bool: True if all permissions restored successfully, False otherwise
        """
        if not permissions:
            print("🔒 No direct table permissions to restore")
            return True

        try:
            print(f"🔒 Restoring {len(permissions)} permissions for table: {table_path}")

            success_count = 0
            for permission in permissions:
                try:
                    principal = permission["principal"]
                    action_type = permission["action_type"]

                    # Skip if essential fields are missing
                    if not principal or not action_type:
                        print(
                            f"  ⚠️  Skipping permission with missing principal or action_type: {permission}"
                        )
                        continue

                    # Build GRANT statement
                    # Handle different principal types (users vs service principals vs groups)
                    if "@" in principal:
                        # Email address - likely a user
                        grant_sql = f"GRANT {action_type} ON TABLE {table_path} TO `{principal}`"
                    elif "-" in principal and len(principal) == 36:
                        # UUID format - likely a service principal
                        grant_sql = f"GRANT {action_type} ON TABLE {table_path} TO `{principal}`"
                    else:
                        # Other format - could be group or special principal
                        grant_sql = f"GRANT {action_type} ON TABLE {table_path} TO `{principal}`"

                    print(f"  🔑 Executing: {grant_sql}")

                    spark.sql(grant_sql)
                    success_count += 1
                    print(f"  ✓ Restored permission: {principal} -> {action_type}")

                except Exception as perm_error:
                    print(
                        f"  ✗ Failed to restore permission {principal} -> {action_type}: {str(perm_error)}"
                    )
                    continue

            print(f"✓ Successfully restored {success_count}/{len(permissions)} permissions")
            return success_count == len(permissions)

        except Exception as e:
            print(f"✗ Error restoring table permissions: {str(e)}")
            return False

    def migrate_legacy_table(spark, table_path, migration_mode="cache"):
        """
        Migrate a legacy Delta table to use column mapping

        Args:
            spark: SparkSession
            table_path: Full table path (catalog.schema.table)
            migration_mode: "cache" (cache data in memory) or "temp" (use temp table)

        Returns:
            bool: True if migration successful, False otherwise
        """
        try:
            print(f"🔄 Starting legacy table migration for: {table_path}")
            print(f"Migration mode: {migration_mode}")

            # Step 0: Backup table permissions
            print("Step 0: Backing up table permissions...")
            permissions = backup_table_permissions(spark, table_path)

            # Step 1: Read existing table data
            print("Step 1: Reading existing table data...")
            existing_df = spark.table(table_path)
            row_count = existing_df.count()
            print(f"Found {row_count} rows in existing table")

            if migration_mode == "cache":
                # Step 2: Cache the data in memory
                print("Step 2: Caching existing data in memory...")
                existing_df.cache()
                # Force evaluation to ensure data is cached
                existing_df.count()
                print("✓ Data cached successfully")

                # Step 3: Drop the existing table
                print("Step 3: Dropping existing table...")
                spark.sql(f"DROP TABLE {table_path}")
                print("✓ Table dropped")

                # Step 4: Recreate table with column mapping
                print("Step 4: Creating new table with column mapping and restoring data...")
                existing_df.write.format("delta").mode("overwrite").option(
                    "delta.columnMapping.mode", "id"
                ).saveAsTable(table_path)
                print("✓ Table recreated with column mapping and data restored")

                # Step 5: Clear cache
                existing_df.unpersist()
                print("✓ Cache cleared")

            elif migration_mode == "temp_table":
                # Step 2: Create temporary table
                temp_table = f"{table_path}_migration_temp"
                print(f"Step 2: Creating temporary table: {temp_table}")

                existing_df.write.format("delta").mode("overwrite").option(
                    "delta.columnMapping.mode", "id"
                ).saveAsTable(temp_table)
                print("✓ Temporary table created")

                # Step 3: Drop original table
                print("Step 3: Dropping original table...")
                spark.sql(f"DROP TABLE {table_path}")
                print("✓ Original table dropped")

                # Step 4: Rename temp table to original name
                print("Step 4: Renaming temporary table...")
                spark.sql(f"ALTER TABLE {temp_table} RENAME TO {table_path}")
                print("✓ Table renamed")

            else:
                raise ValueError(
                    f"Invalid migration_mode: {migration_mode}. Use 'cache' or 'temp_table'"
                )

            # Step 6: Restore table permissions
            print("Step 6: Restoring table permissions...")
            permission_success = restore_table_permissions(spark, table_path, permissions)
            if not permission_success:
                print("⚠️  Some table permissions could not be restored - please check manually")

            # Step 7: Verify migration
            print("Step 7: Verifying migration...")

            # Check table exists
            table_exists = spark.catalog.tableExists(table_path)
            if not table_exists:
                raise Exception(f"Table {table_path} does not exist after migration")
            print(f"Table {table_path} exists")

            # Check table properties
            table_properties = dict(
                spark.sql(f"DESCRIBE DETAIL {table_path}").select("properties").collect()[0][0]
            )
            print(f"Table properties: {table_properties}")

            # Verify column mapping is enabled
            column_mapping_mode = table_properties.get("delta.columnMapping.mode")
            if column_mapping_mode != "id":
                raise Exception(f"Column mapping not enabled. Mode: {column_mapping_mode}")
            print(f"Column mapping mode: {column_mapping_mode}")

            # Verify row count
            new_row_count = spark.table(table_path).count()
            if new_row_count != row_count:
                raise Exception(f"Row count mismatch. Before: {row_count}, After: {new_row_count}")
            print(f"✓ Row count verified: {new_row_count} rows")

            print("✅ Legacy table migration completed successfully!")
            return True

        except Exception as e:
            print(f"❌ Legacy table migration failed: {str(e)}")
            traceback.print_exc()
            return False

    # Validate parameters
    if migrate_legacy_mode.lower() not in ["cache", "temp_table"]:
        raise ValueError(
            f"Invalid migrate_legacy_mode: {migrate_legacy_mode}. Must be 'cache' or 'temp_table'"
        )

    # Step 0: Validate DataFrame (if validation config provided)
    if validate:
        try:
            validate_dataframe(df, validate)
        except AssertionError as e:
            print(f"❌ DataFrame validation failed: {str(e)}")
            raise
        except Exception as e:
            print(f"❌ Unexpected error during validation: {str(e)}")
            raise

    # Step 1: Clean columns and create mapping
    cleaned_df, column_mapping = clean_columns_for_parquet(df)

    if column_mapping:
        print(f"Column mappings applied: {column_mapping}")
    else:
        print("No column cleaning required")

    # Create reverse mapping (original -> cleaned) for merge key translation
    original_to_cleaned = {}
    for cleaned_col, original_col in column_mapping.items():
        original_to_cleaned[original_col] = cleaned_col

    # For columns that weren't changed, add them to the mapping
    for original_col in df.columns:
        if original_col not in original_to_cleaned:
            original_to_cleaned[original_col] = original_col

    print(f"Original to cleaned mapping: {original_to_cleaned}")

    # Step 2: Check table existence and column mapping before proceeding
    print(f"Checking table existence and column mapping for: {table_path}")
    table_exists, column_mapping_enabled, error_message = check_table_exists_and_column_mapping(
        spark, table_path
    )

    # Step 3: Handle legacy table detection (consistent across all save modes)
    if table_exists and not column_mapping_enabled:
        if not migrate_legacy:
            # Default behavior: Error out with helpful message
            legacy_error_message = (
                f"❌ Legacy table detected: {error_message}\n\n"
                f"This table was created without column mapping enabled, which is required for this operation.\n\n"
                f"To migrate this legacy table, you have two options:\n"
                f"1. Set migrate_legacy=True to automatically migrate the table\n"
                f"2. Manually recreate the table with column mapping enabled\n\n"
                f"Migration options:\n"
                f"- migrate_legacy=True, migrate_legacy_mode='cache' (default): Uses memory caching during migration\n"
                f"- migrate_legacy=True, migrate_legacy_mode='temp_table': Creates temporary backup table during migration\n\n"
                f"Note: Table permissions will be automatically preserved during migration.\n\n"
                f"Example: save_df_to_delta_with_column_mapping(spark, df, '{table_path}', migrate_legacy=True)"
            )
            raise ValueError(legacy_error_message)
        else:
            # User opted for migration - migrate the legacy table first
            print(f"🔧 Legacy table migration requested (mode: {migrate_legacy_mode})")
            print("Migrating legacy table first...")

            migration_success = migrate_legacy_table(spark, table_path, migrate_legacy_mode)

            if not migration_success:
                raise RuntimeError(f"Failed to migrate legacy table: {table_path}")

            # Re-check table status after migration
            table_exists, column_mapping_enabled, error_message = (
                check_table_exists_and_column_mapping(spark, table_path)
            )

            if not column_mapping_enabled:
                raise RuntimeError(
                    f"Migration appeared to succeed but column mapping is still not enabled: {error_message}"
                )

            print("✅ Legacy table migration completed successfully")

    # Step 4: Create table with column mapping if it doesn't exist (only for non-overwrite modes)
    if not table_exists and save_mode.lower() != "overwrite":
        # Create table schema DDL
        columns_ddl = []
        for field in cleaned_df.schema.fields:
            columns_ddl.append(f"`{field.name}` {field.dataType.simpleString()}")
        schema_ddl = ", ".join(columns_ddl)

        # Create table with column mapping enabled
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_path} ({schema_ddl})
        USING DELTA
        TBLPROPERTIES (
            'delta.columnMapping.mode' = 'id'
        )
        """

        print(f"Creating Delta table: {table_path}")
        print(f"Schema DDL: {schema_ddl}")
        print(f"Executing SQL: {create_table_sql}")

        spark.sql(create_table_sql)

        # Verify table was created with column mapping
        table_exists, column_mapping_enabled, error_message = check_table_exists_and_column_mapping(
            spark, table_path
        )
        if not column_mapping_enabled:
            raise RuntimeError(
                f"Failed to create table with column mapping enabled: {error_message}"
            )

        print("Table created successfully with column mapping enabled")
    elif table_exists and save_mode.lower() != "overwrite":
        print(f"Table {table_path} already exists with column mapping enabled")

    # Step 5: Save data (if requested)
    if save_data:
        print(f"Save mode: {save_mode}")

        if save_mode.lower() == "append":
            print("Appending data to Delta table...")
            cleaned_df.write.format("delta").mode("append").saveAsTable(table_path)
            print("Data appended successfully!")

        elif save_mode.lower() == "overwrite":
            print("Save mode: overwrite")

            # At this point, either:
            # 1. Table doesn't exist (will be created with column mapping), OR
            # 2. Table exists and has column mapping (migrated or already had it)
            # Legacy tables without migration would have raised an error in Step 3

            print("Overwriting table...")
            write_options = {"format": "delta", "mode": "overwrite", "overwriteSchema": "true"}

            # Enable column mapping for new tables
            if not table_exists:
                write_options["delta.columnMapping.mode"] = "id"
                print("Enabling column mapping for new table")

            # Build and execute write operation
            writer = cleaned_df.write
            for key, value in write_options.items():
                if key == "format":
                    writer = writer.format(value)
                elif key == "mode":
                    writer = writer.mode(value)
                else:
                    writer = writer.option(key, value)

            writer.saveAsTable(table_path)
            print("Table overwritten successfully!")

            # Final verification
            table_exists, column_mapping_enabled, error_message = (
                check_table_exists_and_column_mapping(spark, table_path)
            )
            if column_mapping_enabled:
                print("✓ Column mapping confirmed enabled after overwrite")
            else:
                raise RuntimeError(f"Column mapping not enabled after overwrite: {error_message}")

        elif save_mode.lower() == "merge":
            # Validate merge parameters
            if not merge_keys and not merge_condition:
                raise ValueError(
                    "For merge mode, either 'merge_keys' or 'merge_condition' must be provided"
                )

            # Create temporary view for source data
            temp_view_name = f"temp_source_{table_path.replace('.', '_').replace('-', '_')}"
            cleaned_df.createOrReplaceTempView(temp_view_name)

            # Build merge condition
            if merge_condition:
                condition = merge_condition
                print(f"Using custom merge condition: {condition}")
            else:
                # Validate original merge keys exist in original DataFrame
                missing_keys = [key for key in merge_keys if key not in df.columns]
                if missing_keys:
                    raise ValueError(f"Original merge keys not found in DataFrame: {missing_keys}")

                # Translate original merge keys to cleaned column names
                cleaned_merge_keys = []
                for original_key in merge_keys:
                    cleaned_key = original_to_cleaned[original_key]
                    cleaned_merge_keys.append(cleaned_key)

                print(f"Original merge keys: {merge_keys}")
                print(f"Cleaned merge keys: {cleaned_merge_keys}")

                # Build condition from cleaned merge keys
                conditions = [f"target.`{key}` = source.`{key}`" for key in cleaned_merge_keys]
                condition = " AND ".join(conditions)
                print(f"Generated merge condition: {condition}")

            # Build column list for INSERT and UPDATE using cleaned column names
            insert_columns = ", ".join([f"`{col}`" for col in cleaned_df.columns])
            insert_values = ", ".join([f"source.`{col}`" for col in cleaned_df.columns])
            update_set = ", ".join(
                [f"target.`{col}` = source.`{col}`" for col in cleaned_df.columns]
            )

            # Execute MERGE
            merge_sql = f"""
            MERGE INTO {table_path} AS target
            USING {temp_view_name} AS source
            ON {condition}
            WHEN MATCHED THEN
                UPDATE SET {update_set}
            WHEN NOT MATCHED THEN
                INSERT ({insert_columns})
                VALUES ({insert_values})
            """

            print("Executing MERGE INTO...")
            print(f"MERGE SQL: {merge_sql}")

            spark.sql(merge_sql)
            print("Data merged successfully!")

            # Clean up temporary view
            spark.sql(f"DROP VIEW IF EXISTS {temp_view_name}")

        else:
            raise ValueError(
                f"Invalid save_mode: {save_mode}. Must be 'append', 'overwrite', or 'merge'"
            )
    else:
        print("Skipping data save (save_data=False)")

    return cleaned_df, column_mapping
