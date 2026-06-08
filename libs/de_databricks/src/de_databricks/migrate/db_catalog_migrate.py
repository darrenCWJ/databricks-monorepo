from de_databricks.unitycatalog.db_unity_catalog import assign_catalog_to_workspace


def get_table_comment(spark, catalog, schema, table):
    """Get table comment/description from Unity Catalog metadata.

    Args:
        catalog (str): the catalog name containing the table
        schema (str): the schema name containing the table
        table (str): the table name to retrieve comment for

    Returns:
        str or None: the table comment/description if it exists, None otherwise
    """
    try:
        table_info = spark.sql(f"DESCRIBE TABLE EXTENDED {catalog}.{schema}.{table}").collect()

        for row in table_info:
            if row["col_name"] == "Comment" and row["data_type"] and row["data_type"].strip():
                return row["data_type"].strip()
        return None
    except Exception as e:
        print(f"      ⚠️ Could not get comment for {table}: {str(e)}")
        return None


def get_view_comment(spark, catalog, schema, view):
    """Get view comment/description from Unity Catalog metadata.

    Args:
        catalog (str): the catalog name containing the view
        schema (str): the schema name containing the view
        view (str): the view name to retrieve comment for

    Returns:
        str or None: the view comment/description if it exists, None otherwise
    """
    try:
        view_info = spark.sql(f"DESCRIBE TABLE EXTENDED {catalog}.{schema}.{view}").collect()

        for row in view_info:
            if row["col_name"] == "Comment" and row["data_type"] and row["data_type"].strip():
                return row["data_type"].strip()
        return None
    except Exception as e:
        print(f"      ⚠️ Could not get comment for view {view}: {str(e)}")
        return None


def migrate_catalog_permissions(session, source_catalog, target_catalog):
    """Migrate catalog-level permissions from source to target catalog.

    Retrieves all non-inherited permissions from the source catalog and applies them
    to the target catalog using Unity Catalog permissions API.

    Args:
        session (common.session.CustomSession): authenticated Databricks session
        source_catalog (str): the source catalog name to copy permissions from
        target_catalog (str): the target catalog name to apply permissions to

    Returns:
        None: prints status messages during execution
    """
    try:
        # Get catalog permissions
        response = session.get(f"/api/2.1/unity-catalog/permissions/catalog/{source_catalog}")

        if response.status_code == 200:
            permissions_data = response.json()
            privilege_assignments = permissions_data.get("privilege_assignments", [])

            # Filter out inherited permissions
            non_inherited_permissions = [
                perm for perm in privilege_assignments if not perm.get("inherited", False)
            ]

            if non_inherited_permissions:
                print(
                    f"    Found {len(non_inherited_permissions)} non-inherited catalog permissions"
                )

                # Apply permissions to target catalog
                for perm in non_inherited_permissions:
                    principal = perm["principal"]
                    privileges = perm["privileges"]

                    permission_request = {"changes": [{"principal": principal, "add": privileges}]}

                    perm_response = session.patch(
                        f"/api/2.1/unity-catalog/permissions/catalog/{target_catalog}",
                        json=permission_request,
                    )

                    if perm_response.status_code == 200:
                        print(f"    ✅ Applied permissions for {principal}")
                    else:
                        print(
                            f"    ❌ Failed to apply permissions for {principal}: {perm_response.text}"
                        )
            else:
                print("    No non-inherited catalog permissions found")
        else:
            print(f"    ❌ Failed to get catalog permissions: {response.text}")

    except Exception as e:
        print(f"    ❌ Error migrating catalog permissions: {str(e)}")


def migrate_schema_permissions(session, source_catalog, target_catalog, schema):
    """Migrate schema-level permissions from source to target catalog.

    Retrieves all non-inherited permissions for a specific schema from the source catalog
    and applies them to the corresponding schema in the target catalog.

    Args:
        session (common.session.CustomSession): authenticated Databricks session
        source_catalog (str): the source catalog name to copy permissions from
        target_catalog (str): the target catalog name to apply permissions to
        schema (str): the schema name to migrate permissions for

    Returns:
        None: prints status messages during execution
    """
    try:
        # Get schema permissions
        response = session.get(
            f"/api/2.1/unity-catalog/permissions/schema/{source_catalog}.{schema}"
        )

        if response.status_code == 200:
            permissions_data = response.json()
            privilege_assignments = permissions_data.get("privilege_assignments", [])

            # Filter out inherited permissions
            non_inherited_permissions = [
                perm for perm in privilege_assignments if not perm.get("inherited", False)
            ]

            if non_inherited_permissions:
                print(
                    f"    Found {len(non_inherited_permissions)} non-inherited permissions for schema {schema}"
                )

                # Apply permissions to target schema
                for perm in non_inherited_permissions:
                    principal = perm["principal"]
                    privileges = perm["privileges"]

                    permission_request = {"changes": [{"principal": principal, "add": privileges}]}

                    perm_response = session.patch(
                        f"/api/2.1/unity-catalog/permissions/schema/{target_catalog}.{schema}",
                        json=permission_request,
                    )

                    if perm_response.status_code == 200:
                        print(f"      ✅ Applied permissions for {principal}")
                    else:
                        print(
                            f"      ❌ Failed to apply permissions for {principal}: {perm_response.text}"
                        )

    except Exception as e:
        print(f"    ❌ Error migrating schema permissions for {schema}: {str(e)}")


def migrate_table_permissions(session, source_catalog, target_catalog, schema, table):
    """Migrate table-level permissions from source to target catalog.

    Retrieves all non-inherited permissions for a specific table from the source catalog
    and applies them to the corresponding table in the target catalog.

    Args:
        session (common.session.CustomSession): authenticated Databricks session
        source_catalog (str): the source catalog name to copy permissions from
        target_catalog (str): the target catalog name to apply permissions to
        schema (str): the schema name containing the table
        table (str): the table name to migrate permissions for

    Returns:
        None: prints status messages during execution
    """
    try:
        # Get table permissions
        response = session.get(
            f"/api/2.1/unity-catalog/permissions/table/{source_catalog}.{schema}.{table}"
        )

        if response.status_code == 200:
            permissions_data = response.json()
            privilege_assignments = permissions_data.get("privilege_assignments", [])

            # Filter out inherited permissions
            non_inherited_permissions = [
                perm for perm in privilege_assignments if not perm.get("inherited", False)
            ]

            if non_inherited_permissions:
                print(
                    f"      Found {len(non_inherited_permissions)} non-inherited permissions for table {table}"
                )

                # Apply permissions to target table
                for perm in non_inherited_permissions:
                    principal = perm["principal"]
                    privileges = perm["privileges"]

                    permission_request = {"changes": [{"principal": principal, "add": privileges}]}

                    perm_response = session.patch(
                        f"/api/2.1/unity-catalog/permissions/table/{target_catalog}.{schema}.{table}",
                        json=permission_request,
                    )

                    if perm_response.status_code == 200:
                        print(f"        ✅ Applied permissions for {principal}")
                    else:
                        print(
                            f"        ❌ Failed to apply permissions for {principal}: {perm_response.text}"
                        )

    except Exception as e:
        print(f"      ❌ Error migrating table permissions for {table}: {str(e)}")


def migrate_view_permissions(session, source_catalog, target_catalog, schema, view):
    """Migrate view-level permissions from source to target catalog.

    Retrieves all non-inherited permissions for a specific view from the source catalog
    and applies them to the corresponding view in the target catalog.

    Args:
        session (common.session.CustomSession): authenticated Databricks session
        source_catalog (str): the source catalog name to copy permissions from
        target_catalog (str): the target catalog name to apply permissions to
        schema (str): the schema name containing the view
        view (str): the view name to migrate permissions for

    Returns:
        None: prints status messages during execution
    """
    try:
        # Get view permissions
        response = session.get(
            f"/api/2.1/unity-catalog/permissions/table/{source_catalog}.{schema}.{view}"
        )

        if response.status_code == 200:
            permissions_data = response.json()
            privilege_assignments = permissions_data.get("privilege_assignments", [])

            # Filter out inherited permissions
            non_inherited_permissions = [
                perm for perm in privilege_assignments if not perm.get("inherited", False)
            ]

            if non_inherited_permissions:
                print(
                    f"      Found {len(non_inherited_permissions)} non-inherited permissions for view {view}"
                )

                # Apply permissions to target view
                for perm in non_inherited_permissions:
                    principal = perm["principal"]
                    privileges = perm["privileges"]

                    permission_request = {"changes": [{"principal": principal, "add": privileges}]}

                    perm_response = session.patch(
                        f"/api/2.1/unity-catalog/permissions/table/{target_catalog}.{schema}.{view}",
                        json=permission_request,
                    )

                    if perm_response.status_code == 200:
                        print(f"        ✅ Applied permissions for {principal}")
                    else:
                        print(
                            f"        ❌ Failed to apply permissions for {principal}: {perm_response.text}"
                        )

    except Exception as e:
        print(f"      ❌ Error migrating view permissions for {view}: {str(e)}")


def migrate_volume_permissions(session, source_catalog, target_catalog, schema, volume):
    """Migrate volume-level permissions from source to target catalog.

    Retrieves all non-inherited permissions for a specific volume from the source catalog
    and applies them to the corresponding volume in the target catalog.

    Args:
        session (common.session.CustomSession): authenticated Databricks session
        source_catalog (str): the source catalog name to copy permissions from
        target_catalog (str): the target catalog name to apply permissions to
        schema (str): the schema name containing the volume
        volume (str): the volume name to migrate permissions for

    Returns:
        None: prints status messages during execution
    """
    try:
        # Get volume permissions
        response = session.get(
            f"/api/2.1/unity-catalog/permissions/volume/{source_catalog}.{schema}.{volume}"
        )

        if response.status_code == 200:
            permissions_data = response.json()
            privilege_assignments = permissions_data.get("privilege_assignments", [])

            # Filter out inherited permissions
            non_inherited_permissions = [
                perm for perm in privilege_assignments if not perm.get("inherited", False)
            ]

            if non_inherited_permissions:
                print(
                    f"      Found {len(non_inherited_permissions)} non-inherited permissions for volume {volume}"
                )

                # Apply permissions to target volume
                for perm in non_inherited_permissions:
                    principal = perm["principal"]
                    privileges = perm["privileges"]

                    permission_request = {"changes": [{"principal": principal, "add": privileges}]}

                    perm_response = session.patch(
                        f"/api/2.1/unity-catalog/permissions/volume/{target_catalog}.{schema}.{volume}",
                        json=permission_request,
                    )

                    if perm_response.status_code == 200:
                        print(f"        ✅ Applied permissions for {principal}")
                    else:
                        print(
                            f"        ❌ Failed to apply permissions for {principal}: {perm_response.text}"
                        )

    except Exception as e:
        print(f"      ❌ Error migrating volume permissions for {volume}: {str(e)}")


def create_and_replicate_catalog(spark, session, source_catalog, storage_location):
    """Create new managed catalog and replicate all objects from source catalog with permissions

    Replicate and copy all table, volume, view into a new catalog that newly created managed catalog.
    All permission are replicated

    Args:
        spark (SparkSession): Spark session object
        session (common.session.CustomSession): authenticated Databricks session
        source_catalog (str): the source catalog name to copy permissions from
        storage_location (str): the storage location for the new catalog

    Returns:
        target_catalog (str): the newly created catalog name
    """

    # Generate target catalog name with _v2 suffix
    target_catalog = f"{source_catalog}_v2"

    print(f"Starting catalog replication: {source_catalog} -> {target_catalog}")
    print(f"Storage location: {storage_location}")

    # Step 1: Create new managed catalog
    print(f"Creating managed catalog: {target_catalog}")
    spark.sql(
        f"CREATE CATALOG IF NOT EXISTS {target_catalog} MANAGED LOCATION '{storage_location}'"
    )

    assign_catalog_to_workspace(session, target_catalog)

    # Step 2: Migrate catalog-level permissions
    print("Migrating catalog permissions...")
    migrate_catalog_permissions(session, source_catalog, target_catalog)

    # Step 3: Get all schemas from source catalog
    print("Discovering schemas...")
    schemas_df = spark.sql(f"SHOW SCHEMAS IN {source_catalog}")
    schemas = [
        row.databaseName for row in schemas_df.collect() if row.databaseName != "information_schema"
    ]
    print(f"Found {len(schemas)} schemas")

    # Step 4: Create schemas in target catalog
    print("Creating schemas...")
    for schema in schemas:
        print(f"  Creating schema: {schema}")
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {target_catalog}.{schema}")

    # Step 5: Migrate schema-level permissions
    print("Migrating schema permissions...")
    for schema in schemas:
        migrate_schema_permissions(session, source_catalog, target_catalog, schema)

    # Step 6: Replicate tables (excluding views)
    print("Replicating tables...")
    for schema in schemas:
        # Get all tables (includes both tables and views)
        tables_df = spark.sql(f"SHOW TABLES IN {source_catalog}.{schema}")
        all_tables = [row.tableName for row in tables_df.collect()]

        # Get views separately
        spark.sql(f"USE CATALOG {source_catalog};")
        views_df = spark.sql(f"SHOW VIEWS IN {schema}")
        views = [row.viewName for row in views_df.collect()]

        # Remove views from tables list to get actual tables only
        actual_tables = [table for table in all_tables if table not in views]

        print(f"  Schema {schema}: Found {len(actual_tables)} tables, {len(views)} views")

        for table in actual_tables:
            print(f"  Replicating table: {schema}.{table}")

            # Get table comment
            comment = get_table_comment(spark, source_catalog, schema, table)

            # Create the table with data and comment
            if comment:
                # Escape single quotes in comment
                escaped_comment = comment.replace("'", "''")
                spark.sql(f"""
                    CREATE OR REPLACE TABLE {target_catalog}.{schema}.{table}
                    COMMENT '{escaped_comment}'
                    AS SELECT * FROM {source_catalog}.{schema}.{table}
                """)
                print(f"    ✅ Applied comment: {comment}")
            else:
                spark.sql(f"""
                    CREATE OR REPLACE TABLE {target_catalog}.{schema}.{table}
                    AS SELECT * FROM {source_catalog}.{schema}.{table}
                """)

    # Step 7: Migrate table permissions
    print("Migrating table permissions...")
    for schema in schemas:
        tables_df = spark.sql(f"SHOW TABLES IN {source_catalog}.{schema}")
        all_tables = [row.tableName for row in tables_df.collect()]

        spark.sql(f"USE CATALOG {source_catalog};")
        views_df = spark.sql(f"SHOW VIEWS IN {schema}")
        views = [row.viewName for row in views_df.collect()]

        actual_tables = [table for table in all_tables if table not in views]

        for table in actual_tables:
            migrate_table_permissions(session, source_catalog, target_catalog, schema, table)

    # Step 8: Replicate views
    print("Replicating views...")
    for schema in schemas:
        # Get views in schema
        spark.sql(f"USE CATALOG {source_catalog};")
        views_df = spark.sql(f"SHOW VIEWS IN {schema}")
        views = [row.viewName for row in views_df.collect()]

        for view in views:
            print(f"  Replicating view: {schema}.{view}")

            # Get view comment
            comment = get_view_comment(spark, source_catalog, schema, view)

            # Get view definition
            view_def = spark.sql(f"SHOW CREATE TABLE {source_catalog}.{schema}.{view}").collect()[
                0
            ][0]

            # Replace source catalog with target catalog in view definition
            new_view_def = view_def.replace(f"{source_catalog}.", f"{target_catalog}.")

            # Add comment to the view definition if it exists
            if comment:
                # Escape single quotes in comment
                escaped_comment = comment.replace("'", "''")
                # Insert comment before AS clause
                if " AS " in new_view_def:
                    parts = new_view_def.split(" AS ", 1)
                    new_view_def = f"{parts[0]} COMMENT '{escaped_comment}' AS {parts[1]}"
                print(f"    ✅ Applied comment: {comment}")

            # Replace CREATE VIEW with CREATE OR REPLACE VIEW
            new_view_def = new_view_def.replace("CREATE VIEW ", "CREATE OR REPLACE VIEW ")

            # USE CATALOG statement before running the view definition
            spark.sql(f"USE CATALOG {target_catalog};")
            # Run the create view
            spark.sql(new_view_def)

    # Step 9: Migrate view permissions
    print("Migrating view permissions...")
    for schema in schemas:
        spark.sql(f"USE CATALOG {source_catalog};")
        views_df = spark.sql(f"SHOW VIEWS IN {schema}")
        views = [row.viewName for row in views_df.collect()]

        for view in views:
            migrate_view_permissions(session, source_catalog, target_catalog, schema, view)

    # Step 10: Create volumes
    print("Creating volumes...")
    for schema in schemas:
        # Get volumes in schema
        try:
            volumes_df = spark.sql(f"SHOW VOLUMES IN {source_catalog}.{schema}")
            volumes = [row.volume_name for row in volumes_df.collect()]

            for volume in volumes:
                print(f"  Creating volume: {schema}.{volume}")
                spark.sql(f"CREATE VOLUME IF NOT EXISTS {target_catalog}.{schema}.{volume}")
        except:
            # Schema might not have volumes
            continue

    # Step 11: Migrate volume permissions
    print("Migrating volume permissions...")
    for schema in schemas:
        try:
            volumes_df = spark.sql(f"SHOW VOLUMES IN {source_catalog}.{schema}")
            volumes = [row.volume_name for row in volumes_df.collect()]

            for volume in volumes:
                migrate_volume_permissions(session, source_catalog, target_catalog, schema, volume)
        except:
            continue

    # Step 12: Copy volume files
    print("Copying volume files...")
    for schema in schemas:
        try:
            volumes_df = spark.sql(f"SHOW VOLUMES IN {source_catalog}.{schema}")
            volumes = [row.volume_name for row in volumes_df.collect()]

            for volume in volumes:
                print(f"  Copying files for volume: {schema}.{volume}")
                # List files in source volume
                try:
                    files_df = spark.sql(f"LIST '/Volumes/{source_catalog}/{schema}/{volume}/'")
                    files = files_df.collect()

                    if files:
                        # Copy files using dbutils
                        source_path = f"/Volumes/{source_catalog}/{schema}/{volume}/"
                        target_path = f"/Volumes/{target_catalog}/{schema}/{volume}/"
                        dbutils.fs.cp(source_path, target_path, recurse=True)
                except:
                    # Volume might be empty or inaccessible
                    continue
        except:
            continue

    print("Catalog replication completed successfully!")
    print(f"New catalog '{target_catalog}' is ready for use with migrated permissions")
    return target_catalog
