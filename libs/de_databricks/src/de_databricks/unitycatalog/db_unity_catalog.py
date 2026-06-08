import re

from de_databricks.common.session import *
from de_databricks.common.utils import is_valid_email, print_success_or_error
from de_databricks.iam.db_group import get_user_details


### Get Permissions of a Unity Catalog Object
def get_permissions(session, securable_type: str, securable_name: str) -> dict:
    """Function to get the permissions of a securable_type and securable_name.

    Args:
        session (common.session.CustomSession): custom workspace session
        securable_type (str): catalog | schema | table | storage_credential | external_location | function | share | provider | recipient | metastore | pipeline | volume | connection
        securable_name (str): the full securable_name name, example "uat.gold.table"

    Returns:
        dict: json return of securable permissions
    """
    r = session.get(f"unity-catalog/permissions/{securable_type}/{securable_name}")
    print_success_or_error(r, f"Get permissions for {securable_type} -> {securable_name}")
    return r.json()


### Get effective permissions of a Unity Catalog Object
def get_effective_permissions(session, securable_type: str, securable_name: str) -> dict:
    """Function to gets the effective permissions for a securable. Effective permissions include all object level permissions, and also all inherited permissions.

    Args:
        session (common.session.CustomSession): custom workspace session
        securable_type (str): catalog | schema | table | storage_credential | external_location | function | share | provider | recipient | metastore | pipeline | volume | connection
        securable_name (str): the full securable_name name, example "uat.gold.table"

    Returns:
        dict: json return of securable permissions
    """
    r = session.get(f"unity-catalog/effective-permissions/{securable_type}/{securable_name}")
    print_success_or_error(r, f"Get effective permissions for {securable_type} -> {securable_name}")
    return r.json()


### Update Permissions of a Unity Catalog Object
def update_permissions(
    session,
    securable_type: str,
    securable_name: str,
    operation: str,
    permissions: list,
    principal: str,
) -> dict:
    """Function to update the permissions of a securable_type and securable_name of the given user email or group name.

    Args:
        session (common.session.CustomSession): custom workspace session
        securable_type (str): catalog | schema | table | storage_credential | external_location | function | share | provider | recipient | metastore | pipeline | volume | connection
        securable_name (str): the full securable_name name, example "uat.gold.table"
        operation (str): add | remove
        permissions (list): [...ARRAY...]  Go to https://docs.databricks.com/en/data-governance/unity-catalog/manage-privileges/privileges.html to see what permissions is accepted for the different securable_type
        principal (str): user email or group name

    Returns:
        dict: json return of updated permissions
    """
    if is_valid_email(principal):
        session.update_api_version("2.0")
        principal = get_user_details(session, principal)["Resources"][0]["userName"]
        session.update_api_version("2.1")
    else:
        pass
    r = session.patch(
        f"unity-catalog/permissions/{securable_type}/{securable_name}",
        json={"changes": [{"principal": principal, operation: permissions}]},
    )
    print_success_or_error(
        r,
        f"{operation.title()}ed permissions for {securable_type} -> {securable_name} for principal {principal}",
    )
    return r.json()


def assign_catalog_to_workspace(session, catalog_name: str) -> dict:
    """Function to assign a catalog to a specific workspace by setting it to ISOLATED mode and creating workspace bindings.

    Args:
        session (common.session.CustomSession): custom workspace session
        catalog_name (str): the catalog name to assign
        workspace_id (str): the target workspace ID

    Returns:
        dict: json return of the workspace binding operation
    """

    # Getting workspace_id
    workspace_id = session.workspace_id

    # Step 1: Set catalog to ISOLATED mode
    isolation_r = session.patch(
        f"/api/2.1/unity-catalog/catalogs/{catalog_name}", json={"isolation_mode": "ISOLATED"}
    )
    print_success_or_error(isolation_r, f"Set catalog {catalog_name} to ISOLATED mode")

    if isolation_r.status_code != 200:
        return isolation_r.json()

    # Step 2: Create workspace binding
    bindings_r = session.patch(
        f"/api/2.1/unity-catalog/bindings/catalog/{catalog_name}",
        json={
            "add": [{"workspace_id": int(workspace_id), "binding_type": "BINDING_TYPE_READ_WRITE"}]
        },
    )
    print_success_or_error(
        bindings_r, f"Assigned catalog {catalog_name} to workspace {workspace_id}"
    )

    return bindings_r.json()


def get_catalogs_for_env(session, env):
    """Get all catalogs that match the specified environment suffix.

    Args:
        session (common.session.CustomSession): custom workspace session
        env (str): the environment suffix to filter catalogs by (e.g., 'dev', 'prd', 'stg')

    Returns:
        list: list of catalog objects that have names ending with the specified environment suffix
    """
    try:
        catalogs = session.get("/api/2.1/unity-catalog/catalogs").json().get("catalogs", [])
        # Filter catalogs that end with the specified environment
        env_catalogs = [cat for cat in catalogs if cat["name"].endswith(f"_{env}")]
        return env_catalogs
    except Exception as e:
        print(f"Error fetching catalogs: {e}")
        return []
