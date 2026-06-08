from typing import Dict, Tuple, Union

from de_databricks.common.session import *
from de_databricks.common.utils import CustomResponse, print_success_or_error


### Convert the workspace api session to account api session
def convert_session_account(session):
    """Function to convert workspace api session to account api session that uses OAuth credential of a service principal (this service principal would need to have Account Admin permission) within the Databricks Account

    Args:
        session (common.session.CustomSession): custom workspace session

    Returns:
        common.session.CustomSession: custom account session
    """
    try:
        ### SERVICE PRINCIPAL ID AND SECRET
        client_id = dbutils.secrets.get("admin", "prd_account_principal_client_id")
        client_secret = dbutils.secrets.get("admin", "prd_account_principal_client_secret")
    except Exception as e:
        print(e)
    else:
        url = f"https://accounts.cloud.databricks.com/oidc/accounts/{session.account_id}/v1/token"

        r = requests.post(
            url,
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
            data={"grant_type": "client_credentials", "scope": "all-apis"},
            auth=(f"{client_id}", f"{client_secret}"),
        )
        session.url_base = "https://accounts.cloud.databricks.com/api/2.0/"
        session.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return session


### Create User
### This should never be run technically, as UAT, and PRD is SSO
def create_new_user(session, email: str) -> dict:
    """Function to create user using email, would also set user name as their email. This function was not tested for use in UAT, PRD due to the use of SSO. Unknown effect of creating user access within them triggering the SSO process.

    Args:
        session (common.session.CustomSession): custom account session
        email (str): user email

    Returns:
        dict: json return of create user account
    """
    # Create User (Acct)
    email = email.lower()
    if session.url_base == "https://accounts.cloud.databricks.com/api/2.0/":
        r = session.post(
            f"accounts/{session.account_id}/scim/v2/Users",
            json={
                "userName": email,
                "emails": [{"value": email, "display": email, "primary": True}],
                "displayName": email,
            },
        )
    else:
        r = CustomResponse(405, "Create of new user should be perform in account level")
    print_success_or_error(r, f"Create User (Acct): {email}")
    return r.json()


### Create New Group with Members
def create_new_group(session, group_name: str, email_list: list) -> dict:
    """Function to create a group with users already being assigned to it.

    Args:
        session (common.session.CustomSession): custom account session
        group_name (str): name of group
        email (list): list of user email

    Returns:
        dict: json return of create group
    """
    members = [{"value": get_user_details(session, x)["Resources"][0]["id"]} for x in email_list]
    if session.url_base == "https://accounts.cloud.databricks.com/api/2.0/":
        r = session.post(
            f"accounts/{session.account_id}/scim/v2/Groups",
            json={"displayName": group_name, "members": members},
        )
    else:
        r = session.post(
            "preview/scim/v2/Groups", json={"displayName": group_name, "members": members}
        )
    print_success_or_error(r, f"Create Group (Acct) with members: {group_name}")
    return r.json()


### Update Group Membership in group
def update_group_details_members(
    session, group_name: str, email_list: list, operation: str, sp_list=None
) -> dict:
    """Function to add users into a group.

    Args:
        session (common.session.CustomSession): custom account session
        operation (str): expected input "add" or "remove" or "replace" members from given group
        group_name (str): name of group
        email (list): list of user email

    Returns:
        dict: json return of add users to group
    """
    members = [{"value": get_user_details(session, x)["Resources"][0]["id"]} for x in email_list]
    group_id = list_group_details(session, group_name)["Resources"][0]["id"]

    if sp_list:
        members += [
            {"value": get_service_principal_details(session, x)["Resources"][0]["id"]}
            for x in sp_list
        ]

    if operation == "remove":
        json_dict = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": operation, "path": "members", "value": {"members": members}}],
        }
    elif operation in ("add", "replace"):
        json_dict = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": operation, "value": {"members": members}}],
        }

    if session.url_base == "https://accounts.cloud.databricks.com/api/2.0/":
        r = session.patch(
            f"accounts/{session.account_id}/scim/v2/Groups/{group_id}", json=json_dict
        )
    else:
        r = session.patch(f"preview/scim/v2/Groups/{group_id}", json=json_dict)
    print_success_or_error(r, f"{operation.title()} Group Members: {group_name}")
    return r.json()


### List Group Details
def list_group_details(session, group_name: str) -> str:
    """Function to get group details, that equal the given group name.

    Args:
        session (common.session.CustomSession): custom account session
        group_name (str): name of group

    Returns:
        str: group_id
    """
    if session.url_base == "https://accounts.cloud.databricks.com/api/2.0/":
        r = session.get(
            f"accounts/{session.account_id}/scim/v2/Groups",
            params={"filter": f"displayName eq {group_name}"},
        )
    else:
        r = session.get("preview/scim/v2/Groups", params={"filter": f"displayName eq {group_name}"})

    print_success_or_error(r, f"List Group Details: {group_name}")
    try:
        if r.json()["totalResults"] >= 0:
            return r.json()
    except:
        raise ValueError("get_group_id api call failed")


### Get User (Acct) Id
def get_user_details(session, user_email: str) -> str:
    """Function to get user details for the given user name.

    Args:
        session (common.session.CustomSession): custom account session
        user_email (str): email of user

    Returns:
        str: user_id
    """
    if session.url_base == "https://accounts.cloud.databricks.com/api/2.0/":
        r = session.get(
            f"accounts/{session.account_id}/scim/v2/Users",
            params={"filter": f"emails.value eq {user_email}"},
        )
    else:
        r = session.get("preview/scim/v2/Users", params={"filter": f"emails.value eq {user_email}"})
    print_success_or_error(r, f"Get User (Acct) Id: {user_email}")

    try:
        if r.json()["totalResults"] >= 0:
            return r.json()
    except:
        raise ValueError("get_user_id api call failed")


def get_service_principal_details(session, display_name, filter_by="displayName"):
    if session.url_base == "https://accounts.cloud.databricks.com/api/2.0/":
        r = session.get(
            f"accounts/{session.account_id}/scim/v2/ServicePrincipals",
            params={"filter": f"{filter_by} eq {display_name}"},
        )
    else:
        r = session.get(
            "preview/scim/v2/ServicePrincipals", params={"filter": f"displayName eq {display_name}"}
        )
    print_success_or_error(r, f"Get Service Principal (Acct) Id: {display_name}")

    try:
        if r.json()["totalResults"] >= 0:
            return r.json()
    except:
        raise ValueError("get_service_principal api call failed")


def check_identity_type(
    session, identity: str, cache: dict = None
) -> tuple[str, dict | None, dict]:
    """
    Check if the given string is a user email, service principal name/id, or group name.

    Args:
        session (common.session.CustomSession): custom account session
        identity (str): string to check (email, service principal name/id, or group name)
        cache (Dict, optional): Dictionary to store cached results

    Returns:
        Tuple[str, Union[Dict, None], Dict]: A tuple containing:
            - str: 'user', 'service_principal', 'group', or 'unknown'
            - Dict or None: The API response data if available, None for UUID matches or unknown types
            - Dict: Updated cache dictionary
    """
    # Initialize cache if None
    cache = cache or {}

    # Check if result is in cache
    if identity in cache:
        return cache[identity][0], cache[identity][1], cache

    # If not in cache, proceed with API calls
    # Then check if it's a user (email format)
    try:
        user_result = get_user_details(session, identity)
        if user_result.get("totalResults", 0) > 0:
            cache[identity] = ("user", user_result)
            return "user", user_result, cache
    except ValueError:
        pass

    # Check if it's a service principal (try both displayName and applicationId)
    try:
        # Try displayName first
        sp_result = get_service_principal_details(session, identity, filter_by="displayName")
        if sp_result.get("totalResults", 0) > 0:
            cache[identity] = ("service_principal", sp_result)
            return "service_principal", sp_result, cache

        # If not found, try applicationId
        sp_result = get_service_principal_details(session, identity, filter_by="applicationId")
        if sp_result.get("totalResults", 0) > 0:
            cache[identity] = ("service_principal", sp_result)
            return "service_principal", sp_result, cache
    except ValueError:
        pass

    # Finally check if it's a group
    try:
        group_result = list_group_details(session, identity)
        if group_result.get("totalResults", 0) > 0:
            cache[identity] = ("group", group_result)
            return "group", group_result, cache
    except ValueError:
        pass

    # Cache unknown results too
    cache[identity] = ("unknown", None)
    return "unknown", None, cache


### Create or update permissions assignment
### This does not include providing workspace entitlement
### Please remember to also run assign_entitement_group in group_ws
def create_update_permissions_assignment(session, group_name: str) -> dict:
    """Function to assign group into workspace depended upon the environment that the code is run. This function does not actually grant entitlement within the workspace, such as databricks-sql-access or workspace-access. It just add the group from account level into the workspace level.

    Args:
        session (common.session.CustomSession): custom account session
        group_name (str): name of group

    Returns:
        dict: json return of assigned group to workspace
    """
    group_id = list_group_details(session, group_name)["Resources"][0]["id"]
    if session.url_base == "https://accounts.cloud.databricks.com/api/2.0/":
        r = session.put(
            f"accounts/{session.account_id}/workspaces/{session.workspace_id}/permissionassignments/principals/{group_id}",
            json={"permissions": ["USER"]},
        )
    else:
        r = CustomResponse(
            405,
            "Create or update permissions assignment is not available in workspace api, please use account api",
        )
    print_success_or_error(r, f"Assign Group to Dev Workspace (Acct): {group_name}")
    return r.json()


### Update group details entitlements
def update_group_details_entitlements(session, group_name: str, entitlements: str) -> dict:
    """Function to update group details entitlements within the workspace, this function should be run within the workspace. It would provide the user that member of the group access to workspace-access and databricks-sql-access.

    Args:
        session (common.session.CustomSession): custom account session
        group_name (str): name of group
        entitlements (str): expected input "platform_access" or "data_access"

    Returns:
        dict: json return of update group entitlements in workspace
    """
    group_id = list_group_details(session, group_name)["Resources"][0]["id"]
    if entitlements == "platform_access":
        entitlements_list = [{"value": "workspace-access"}, {"value": "databricks-sql-access"}]
    elif entitlements == "data_access":
        entitlements_list = [{"value": "databricks-sql-access"}]

    if session.url_base == "https://accounts.cloud.databricks.com/api/2.0/":
        r = CustomResponse(
            405,
            "Update of group entitlement is not available in account api, please use workspace api",
        )
    else:
        r = session.patch(
            f"preview/scim/v2/Groups/{group_id}",
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [{"op": "add", "value": {"entitlements": entitlements_list}}],
            },
        )
    print_success_or_error(r, f"Update Group Details Entitlements: {group_name}")
    return r.json()


### Delete a Group
def delete_group(session, group_name: str) -> dict:
    """Function to delete a group.

    Args:
        session (common.session.CustomSession): custom account session
        group_name (str): name of group

    Returns:
        dict: json return of deleted group
    """
    group_id = list_group_details(session, group_name)["Resources"][0]["id"]
    if session.url_base == "https://accounts.cloud.databricks.com/api/2.0/":
        r = session.delete(f"accounts/{session.account_id}/scim/v2/Groups/{group_id}")
    else:
        r = session.delete(f"preview/scim/v2/Groups/{group_id}")
    print_success_or_error(r, f"Housekeeping Group (Acct): {group_name}")
    return r
