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
