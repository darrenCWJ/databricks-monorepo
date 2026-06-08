"""Unity Catalog permission, ownership, and tagging operations.

All functions require spark as first argument.
"""

from pyspark.sql import SparkSession
from pyspark.sql.utils import AnalysisException

from de_toolbox.catalog import get_catalog
from de_toolbox.validation import format_object_principal


def set_securable_object_tag(
    spark: SparkSession,
    meta_global: dict,
    meta_local: dict,
    object_full_path: str,
) -> None:
    """Set tags on a Databricks table or volume.

    Merges global-level and object-level tags, then applies via ALTER statement.

    Args:
        spark: Active SparkSession.
        meta_global: Top-level config dict (may contain "tags" key).
        meta_local: Object-level config dict (may contain "tags" key with "asset_type").
        object_full_path: Fully qualified path (catalog.schema.object).
    """
    global_tags = meta_global.get("tags", {})
    local_tags = meta_local.get("tags", {})
    object_tags = {**global_tags, **local_tags}

    if not object_tags:
        print(f"No tags to set for {object_full_path} in config")
        return

    tags_sql = ", ".join([f"'{k.lower()}'='{v.lower()}'" for k, v in object_tags.items()])

    asset_type = object_tags.get("asset_type", "").lower()
    valid_asset_types = ("table", "volume")
    if asset_type not in valid_asset_types:
        raise ValueError(f"asset_type must be one of {valid_asset_types}, but got '{asset_type}'")

    if asset_type == "table":
        sql_command = f"ALTER TABLE {object_full_path} SET TAGS ({tags_sql})"
    else:
        sql_command = f"ALTER VOLUME {object_full_path} SET TAGS ({tags_sql})"

    try:
        spark.sql(sql_command)
        print(f"Successfully set tags for {asset_type} {object_full_path}")
    except AnalysisException as e:
        print(f"Error setting tags for {asset_type} {object_full_path}: {str(e)}")


def change_securable_object_owner(
    spark: SparkSession,
    meta_global: dict,
    meta_local: dict,
    project: str,
    env: str,
    object_full_path: str,
) -> None:
    """Change ownership of a Unity Catalog table or volume.

    Args:
        spark: Active SparkSession.
        meta_global: Top-level config dict (must contain "principal_owner" if ownership is desired).
        meta_local: Object-level config dict (must contain tags.asset_type).
        project: Project name for template substitution.
        env: Environment (dev, stg, prd).
        object_full_path: Fully qualified path (catalog.schema.object).
    """
    object_principal = meta_global.get("principal_owner", "")

    if not object_principal:
        print(f"No principal owner to set for {object_full_path} in config")
        return

    object_principal = format_object_principal(object_principal, env, project)

    asset_type = meta_local.get("tags", {}).get("asset_type", "").lower()
    valid_asset_types = ("table", "volume")
    if asset_type not in valid_asset_types:
        raise ValueError(f"asset_type must be one of {valid_asset_types}, but got '{asset_type}'")

    if asset_type == "table":
        sql_command = f"ALTER TABLE {object_full_path} SET OWNER TO {object_principal}"
    else:
        sql_command = f"ALTER VOLUME {object_full_path} SET OWNER TO {object_principal}"

    try:
        spark.sql(sql_command)
        print(f"Successfully set owner {object_principal} for {asset_type} {object_full_path}")
    except AnalysisException as e:
        print(
            f"Error setting owner {object_principal} for {asset_type} {object_full_path}: {str(e)}"
        )


def grant_securable_object_permission_in_dev(
    spark: SparkSession,
    meta_global: dict,
    project: str,
    env: str,
    object_full_path: str,
) -> None:
    """Grant permissions on a table — only in DEV environment.

    In staging/production, use the Data Access Framework instead.

    Args:
        spark: Active SparkSession.
        meta_global: Config dict with "permission_global" list and "project" key.
        project: Project name.
        env: Environment — only "dev" will apply grants.
        object_full_path: Fully qualified table path.
    """
    if env.lower() != "dev":
        print(
            f"Default configuration-driven permission only applicable for DEV environment, "
            f"for STG|PRD please use the Data Access Framework to implement for {object_full_path}"
        )
        return

    permission_global = meta_global.get("permission_global", [])

    if not permission_global:
        print(f"No permission to grant for {object_full_path} in config")
        return

    project = meta_global["project"]

    for each_permission in permission_global:
        permission_principal = each_permission.get("principal", "")
        permission_type = each_permission.get("type", [])

        permission_principal = format_object_principal(permission_principal, env, project)

        for each_permission_type in permission_type:
            sql_command = (
                f"GRANT {each_permission_type} ON TABLE {object_full_path} "
                f"TO {permission_principal}"
            )
            try:
                spark.sql(sql_command)
                print(
                    f"Successfully grant {each_permission_type} to "
                    f"{permission_principal} for table {object_full_path}"
                )
            except AnalysisException as e:
                print(
                    f"Error in granting {each_permission_type} to "
                    f"{permission_principal} for table {object_full_path}: {str(e)}"
                )


def grant_permission(spark: SparkSession, meta: dict, env: str) -> None:
    """Grant catalog-level privileges to project owners group.

    Args:
        spark: Active SparkSession.
        meta: Metadata dict with "project" key.
        env: Environment (dev, stg, prd).
    """
    project = meta["project"]
    catalog = get_catalog(project, env)
    # Owners
    owners = f"{env}_{project}_owners"
    # TODO: need to remove this function once FIN domain removed it from their silver layer
    # TODO: Add sub-domain owners / users / viewers
    # Grant privileges to groups
    # spark.sql(f"GRANT ALL PRIVILEGES ON CATALOG {catalog} TO {owners}")
