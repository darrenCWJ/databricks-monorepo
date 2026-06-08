from pyspark.testing.utils import assertDataFrameEqual

from de_databricks.common.session import (
    create_databricks_session,
    create_databricks_workspace_session,
)


def validate_catalog_replication(spark, source_catalog, target_catalog):
    """Validate that all objects and permissions were successfully replicated between catalogs"""

    print(f"Starting validation: {source_catalog} vs {target_catalog}")
    validation_results = {
        "schemas": {"match": True, "details": []},
        "tables": {"match": True, "details": []},
        "views": {"match": True, "details": []},
        "volumes": {"match": True, "details": []},
        "table_data": {"match": True, "details": []},
        "permissions": {"match": True, "details": []},
    }

    # Get Workspace session for permission validation
    ws_session = create_databricks_session()

    # Step 1: Validate schemas
    print("Validating schemas...")
    source_schemas_df = spark.sql(f"SHOW SCHEMAS IN {source_catalog}")
    target_schemas_df = spark.sql(f"SHOW SCHEMAS IN {target_catalog}")

    source_schemas = set(
        [
            row.databaseName
            for row in source_schemas_df.collect()
            if row.databaseName != "information_schema"
        ]
    )
    target_schemas = set(
        [
            row.databaseName
            for row in target_schemas_df.collect()
            if row.databaseName != "information_schema"
        ]
    )

    missing_schemas = source_schemas - target_schemas
    extra_schemas = target_schemas - source_schemas

    if missing_schemas or extra_schemas:
        validation_results["schemas"]["match"] = False
        if missing_schemas:
            validation_results["schemas"]["details"].append(
                f"Missing schemas in target: {missing_schemas}"
            )
        if extra_schemas:
            validation_results["schemas"]["details"].append(
                f"Extra schemas in target: {extra_schemas}"
            )
    else:
        validation_results["schemas"]["details"].append(f"All {len(source_schemas)} schemas match")

    # Step 2: Validate tables
    print("Validating tables...")
    for schema in source_schemas.intersection(target_schemas):
        try:
            source_tables_df = spark.sql(f"SHOW TABLES IN {source_catalog}.{schema}")
            target_tables_df = spark.sql(f"SHOW TABLES IN {target_catalog}.{schema}")

            source_tables = set([row.tableName for row in source_tables_df.collect()])
            target_tables = set([row.tableName for row in target_tables_df.collect()])

            missing_tables = source_tables - target_tables
            extra_tables = target_tables - source_tables

            if missing_tables:
                validation_results["tables"]["match"] = False
                validation_results["tables"]["details"].append(
                    f"Schema {schema} - Missing tables: {missing_tables}"
                )
            if extra_tables:
                validation_results["tables"]["match"] = False
                validation_results["tables"]["details"].append(
                    f"Schema {schema} - Extra tables: {extra_tables}"
                )
            if not missing_tables and not extra_tables and source_tables:
                validation_results["tables"]["details"].append(
                    f"Schema {schema} - All {len(source_tables)} tables match"
                )
        except Exception as e:
            validation_results["tables"]["match"] = False
            validation_results["tables"]["details"].append(
                f"Schema {schema} - Error validating tables: {str(e)}"
            )

    # Step 3: Validate views
    print("Validating views...")
    for schema in source_schemas.intersection(target_schemas):
        try:
            spark.sql(f"USE CATALOG {source_catalog}")
            source_views_df = spark.sql(f"SHOW VIEWS IN {schema}")
            spark.sql(f"USE CATALOG {target_catalog}")
            target_views_df = spark.sql(f"SHOW VIEWS IN {schema}")

            source_views = set([row.viewName for row in source_views_df.collect()])
            target_views = set([row.viewName for row in target_views_df.collect()])

            missing_views = source_views - target_views
            extra_views = target_views - source_views

            if missing_views:
                validation_results["views"]["match"] = False
                validation_results["views"]["details"].append(
                    f"Schema {schema} - Missing views: {missing_views}"
                )
            if extra_views:
                validation_results["views"]["match"] = False
                validation_results["views"]["details"].append(
                    f"Schema {schema} - Extra views: {extra_views}"
                )
            if not missing_views and not extra_views and source_views:
                validation_results["views"]["details"].append(
                    f"Schema {schema} - All {len(source_views)} views match"
                )
        except Exception as e:
            validation_results["views"]["match"] = False
            validation_results["views"]["details"].append(
                f"Schema {schema} - Error validating views: {str(e)}"
            )

    # Step 4: Validate volumes
    print("Validating volumes...")
    for schema in source_schemas.intersection(target_schemas):
        try:
            source_volumes_df = spark.sql(f"SHOW VOLUMES IN {source_catalog}.{schema}")
            target_volumes_df = spark.sql(f"SHOW VOLUMES IN {target_catalog}.{schema}")

            source_volumes = set([row.volume_name for row in source_volumes_df.collect()])
            target_volumes = set([row.volume_name for row in target_volumes_df.collect()])

            missing_volumes = source_volumes - target_volumes
            extra_volumes = target_volumes - source_volumes

            if missing_volumes:
                validation_results["volumes"]["match"] = False
                validation_results["volumes"]["details"].append(
                    f"Schema {schema} - Missing volumes: {missing_volumes}"
                )
            if extra_volumes:
                validation_results["volumes"]["match"] = False
                validation_results["volumes"]["details"].append(
                    f"Schema {schema} - Extra volumes: {extra_volumes}"
                )
            if not missing_volumes and not extra_volumes and source_volumes:
                validation_results["volumes"]["details"].append(
                    f"Schema {schema} - All {len(source_volumes)} volumes match"
                )
        except Exception as e:
            # Schema might not have volumes, which is normal
            if "volumes" not in str(e).lower():
                validation_results["volumes"]["match"] = False
                validation_results["volumes"]["details"].append(
                    f"Schema {schema} - Error validating volumes: {str(e)}"
                )

    # Step 5: Validate table data (content and schema)
    print("Validating table data (content and schema)...")
    for schema in source_schemas.intersection(target_schemas):
        try:
            source_tables_df = spark.sql(f"SHOW TABLES IN {source_catalog}.{schema}")
            source_tables = [row.tableName for row in source_tables_df.collect()]

            for table in source_tables:
                try:
                    # Read both tables as DataFrames
                    source_df = spark.table(f"{source_catalog}.{schema}.{table}")
                    target_df = spark.table(f"{target_catalog}.{schema}.{table}")

                    # Use assertDataFrameEqual for comprehensive comparison
                    try:
                        assertDataFrameEqual(source_df, target_df)
                        row_count = source_df.count()
                        validation_results["table_data"]["details"].append(
                            f"Table {schema}.{table} - Data and schema match perfectly ({row_count} rows)"
                        )
                    except AssertionError as ae:
                        validation_results["table_data"]["match"] = False
                        validation_results["table_data"]["details"].append(
                            f"Table {schema}.{table} - Data/schema mismatch: {str(ae)}"
                        )

                except Exception as e:
                    validation_results["table_data"]["match"] = False
                    validation_results["table_data"]["details"].append(
                        f"Table {schema}.{table} - Error comparing data: {str(e)}"
                    )
        except Exception as e:
            validation_results["table_data"]["match"] = False
            validation_results["table_data"]["details"].append(
                f"Schema {schema} - Error validating table data: {str(e)}"
            )

    # Step 6: Validate permissions
    print("Validating permissions...")

    # Validate catalog permissions
    catalog_perm_match = validate_catalog_permissions(
        ws_session, source_catalog, target_catalog, validation_results
    )

    # Validate schema permissions
    for schema in source_schemas.intersection(target_schemas):
        schema_perm_match = validate_schema_permissions(
            ws_session, source_catalog, target_catalog, schema, validation_results
        )

        # Validate table permissions
        try:
            source_tables_df = spark.sql(f"SHOW TABLES IN {source_catalog}.{schema}")
            all_tables = [row.tableName for row in source_tables_df.collect()]

            # Get views to separate from tables
            spark.sql(f"USE CATALOG {source_catalog}")
            views_df = spark.sql(f"SHOW VIEWS IN {schema}")
            views = [row.viewName for row in views_df.collect()]

            # Validate table permissions (excluding views)
            actual_tables = [table for table in all_tables if table not in views]
            for table in actual_tables:
                validate_table_permissions(
                    ws_session, source_catalog, target_catalog, schema, table, validation_results
                )

            # Validate view permissions
            for view in views:
                validate_view_permissions(
                    ws_session, source_catalog, target_catalog, schema, view, validation_results
                )

        except Exception as e:
            validation_results["permissions"]["match"] = False
            validation_results["permissions"]["details"].append(
                f"Schema {schema} - Error validating table/view permissions: {str(e)}"
            )

        # Validate volume permissions
        try:
            source_volumes_df = spark.sql(f"SHOW VOLUMES IN {source_catalog}.{schema}")
            volumes = [row.volume_name for row in source_volumes_df.collect()]

            for volume in volumes:
                validate_volume_permissions(
                    ws_session, source_catalog, target_catalog, schema, volume, validation_results
                )

        except Exception as e:
            # Schema might not have volumes, which is normal
            if "volumes" not in str(e).lower():
                validation_results["permissions"]["match"] = False
                validation_results["permissions"]["details"].append(
                    f"Schema {schema} - Error validating volume permissions: {str(e)}"
                )

    # Print validation summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    overall_success = True
    for category, result in validation_results.items():
        status = "✓ PASS" if result["match"] else "✗ FAIL"
        print(f"{category.upper()}: {status}")
        for detail in result["details"]:
            print(f"  - {detail}")
        print()
        if not result["match"]:
            overall_success = False

    print("=" * 60)
    if overall_success:
        print("🎉 OVERALL VALIDATION: SUCCESS - All objects and permissions replicated correctly!")
    else:
        print("⚠️  OVERALL VALIDATION: FAILED - Some issues found above")
    print("=" * 60)

    return validation_results


def validate_catalog_permissions(session, source_catalog, target_catalog, validation_results):
    """Validate catalog-level permissions match"""
    try:
        # Get source catalog permissions
        source_response = session.get(
            f"/api/2.1/unity-catalog/permissions/catalog/{source_catalog}"
        )
        target_response = session.get(
            f"/api/2.1/unity-catalog/permissions/catalog/{target_catalog}"
        )

        if source_response.status_code == 200 and target_response.status_code == 200:
            source_perms = source_response.json().get("privilege_assignments", [])
            target_perms = target_response.json().get("privilege_assignments", [])

            # Filter non-inherited permissions
            source_non_inherited = {
                perm["principal"]: sorted(perm["privileges"])
                for perm in source_perms
                if not perm.get("inherited", False)
            }
            target_non_inherited = {
                perm["principal"]: sorted(perm["privileges"])
                for perm in target_perms
                if not perm.get("inherited", False)
            }

            if source_non_inherited == target_non_inherited:
                validation_results["permissions"]["details"].append(
                    f"Catalog permissions match - {len(source_non_inherited)} principals"
                )
                return True
            else:
                validation_results["permissions"]["match"] = False

                # Find differences
                missing_principals = set(source_non_inherited.keys()) - set(
                    target_non_inherited.keys()
                )
                extra_principals = set(target_non_inherited.keys()) - set(
                    source_non_inherited.keys()
                )

                if missing_principals:
                    validation_results["permissions"]["details"].append(
                        f"Catalog - Missing principals in target: {missing_principals}"
                    )
                if extra_principals:
                    validation_results["permissions"]["details"].append(
                        f"Catalog - Extra principals in target: {extra_principals}"
                    )

                # Check privilege differences for common principals
                common_principals = set(source_non_inherited.keys()) & set(
                    target_non_inherited.keys()
                )
                for principal in common_principals:
                    if source_non_inherited[principal] != target_non_inherited[principal]:
                        validation_results["permissions"]["details"].append(
                            f"Catalog - Principal {principal} privilege mismatch: "
                            f"source={source_non_inherited[principal]}, target={target_non_inherited[principal]}"
                        )
                return False
        else:
            validation_results["permissions"]["match"] = False
            validation_results["permissions"]["details"].append(
                f"Catalog - Error getting permissions: source={source_response.status_code}, target={target_response.status_code}"
            )
            return False

    except Exception as e:
        validation_results["permissions"]["match"] = False
        validation_results["permissions"]["details"].append(
            f"Catalog - Error validating permissions: {str(e)}"
        )
        return False


def validate_schema_permissions(
    session, source_catalog, target_catalog, schema, validation_results
):
    """Validate schema-level permissions match"""
    try:
        source_response = session.get(
            f"/api/2.1/unity-catalog/permissions/schema/{source_catalog}.{schema}"
        )
        target_response = session.get(
            f"/api/2.1/unity-catalog/permissions/schema/{target_catalog}.{schema}"
        )

        if source_response.status_code == 200 and target_response.status_code == 200:
            source_perms = source_response.json().get("privilege_assignments", [])
            target_perms = target_response.json().get("privilege_assignments", [])

            # Filter non-inherited permissions
            source_non_inherited = {
                perm["principal"]: sorted(perm["privileges"])
                for perm in source_perms
                if not perm.get("inherited", False)
            }
            target_non_inherited = {
                perm["principal"]: sorted(perm["privileges"])
                for perm in target_perms
                if not perm.get("inherited", False)
            }

            if source_non_inherited == target_non_inherited:
                if source_non_inherited:  # Only log if there are permissions
                    validation_results["permissions"]["details"].append(
                        f"Schema {schema} permissions match - {len(source_non_inherited)} principals"
                    )
                return True
            else:
                validation_results["permissions"]["match"] = False
                validation_results["permissions"]["details"].append(
                    f"Schema {schema} - Permission mismatch: source={len(source_non_inherited)}, target={len(target_non_inherited)} principals"
                )
                return False
        else:
            validation_results["permissions"]["match"] = False
            validation_results["permissions"]["details"].append(
                f"Schema {schema} - Error getting permissions: source={source_response.status_code}, target={target_response.status_code}"
            )
            return False

    except Exception as e:
        validation_results["permissions"]["match"] = False
        validation_results["permissions"]["details"].append(
            f"Schema {schema} - Error validating permissions: {str(e)}"
        )
        return False


def validate_table_permissions(
    session, source_catalog, target_catalog, schema, table, validation_results
):
    """Validate table-level permissions match"""
    try:
        source_response = session.get(
            f"/api/2.1/unity-catalog/permissions/table/{source_catalog}.{schema}.{table}"
        )
        target_response = session.get(
            f"/api/2.1/unity-catalog/permissions/table/{target_catalog}.{schema}.{table}"
        )

        if source_response.status_code == 200 and target_response.status_code == 200:
            source_perms = source_response.json().get("privilege_assignments", [])
            target_perms = target_response.json().get("privilege_assignments", [])

            # Filter non-inherited permissions
            source_non_inherited = {
                perm["principal"]: sorted(perm["privileges"])
                for perm in source_perms
                if not perm.get("inherited", False)
            }
            target_non_inherited = {
                perm["principal"]: sorted(perm["privileges"])
                for perm in target_perms
                if not perm.get("inherited", False)
            }

            if source_non_inherited != target_non_inherited:
                validation_results["permissions"]["match"] = False
                validation_results["permissions"]["details"].append(
                    f"Table {schema}.{table} - Permission mismatch: source={len(source_non_inherited)}, target={len(target_non_inherited)} principals"
                )
                return False
            elif source_non_inherited:  # Only log if there are permissions
                validation_results["permissions"]["details"].append(
                    f"Table {schema}.{table} permissions match - {len(source_non_inherited)} principals"
                )
            return True

    except Exception as e:
        validation_results["permissions"]["match"] = False
        validation_results["permissions"]["details"].append(
            f"Table {schema}.{table} - Error validating permissions: {str(e)}"
        )
        return False


def validate_view_permissions(
    session, source_catalog, target_catalog, schema, view, validation_results
):
    """Validate view-level permissions match"""
    try:
        source_response = session.get(
            f"/api/2.1/unity-catalog/permissions/table/{source_catalog}.{schema}.{view}"
        )
        target_response = session.get(
            f"/api/2.1/unity-catalog/permissions/table/{target_catalog}.{schema}.{view}"
        )

        if source_response.status_code == 200 and target_response.status_code == 200:
            source_perms = source_response.json().get("privilege_assignments", [])
            target_perms = target_response.json().get("privilege_assignments", [])

            # Filter non-inherited permissions
            source_non_inherited = {
                perm["principal"]: sorted(perm["privileges"])
                for perm in source_perms
                if not perm.get("inherited", False)
            }
            target_non_inherited = {
                perm["principal"]: sorted(perm["privileges"])
                for perm in target_perms
                if not perm.get("inherited", False)
            }

            if source_non_inherited != target_non_inherited:
                validation_results["permissions"]["match"] = False
                validation_results["permissions"]["details"].append(
                    f"View {schema}.{view} - Permission mismatch: source={len(source_non_inherited)}, target={len(target_non_inherited)} principals"
                )
                return False
            elif source_non_inherited:  # Only log if there are permissions
                validation_results["permissions"]["details"].append(
                    f"View {schema}.{view} permissions match - {len(source_non_inherited)} principals"
                )
            return True

    except Exception as e:
        validation_results["permissions"]["match"] = False
        validation_results["permissions"]["details"].append(
            f"View {schema}.{view} - Error validating permissions: {str(e)}"
        )
        return False


def validate_volume_permissions(
    session, source_catalog, target_catalog, schema, volume, validation_results
):
    """Validate volume-level permissions match"""
    try:
        source_response = session.get(
            f"/api/2.1/unity-catalog/permissions/volume/{source_catalog}.{schema}.{volume}"
        )
        target_response = session.get(
            f"/api/2.1/unity-catalog/permissions/volume/{target_catalog}.{schema}.{volume}"
        )

        if source_response.status_code == 200 and target_response.status_code == 200:
            source_perms = source_response.json().get("privilege_assignments", [])
            target_perms = target_response.json().get("privilege_assignments", [])

            # Filter non-inherited permissions
            source_non_inherited = {
                perm["principal"]: sorted(perm["privileges"])
                for perm in source_perms
                if not perm.get("inherited", False)
            }
            target_non_inherited = {
                perm["principal"]: sorted(perm["privileges"])
                for perm in target_perms
                if not perm.get("inherited", False)
            }

            if source_non_inherited != target_non_inherited:
                validation_results["permissions"]["match"] = False
                validation_results["permissions"]["details"].append(
                    f"Volume {schema}.{volume} - Permission mismatch: source={len(source_non_inherited)}, target={len(target_non_inherited)} principals"
                )
                return False
            elif source_non_inherited:  # Only log if there are permissions
                validation_results["permissions"]["details"].append(
                    f"Volume {schema}.{volume} permissions match - {len(source_non_inherited)} principals"
                )
            return True

    except Exception as e:
        validation_results["permissions"]["match"] = False
        validation_results["permissions"]["details"].append(
            f"Volume {schema}.{volume} - Error validating permissions: {str(e)}"
        )
        return False
