import re
import time

from de_databricks.common.session import *
from de_databricks.common.utils import print_success_or_error


def create_or_get_service_principal(session, display_name):

    # Get Service Principal by Name
    service_principals = {
        resource["displayName"]: resource
        for resource in session.get("preview/scim/v2/ServicePrincipals").json().get("Resources", [])
    }

    # Return Service Principal if exists
    if display_name not in service_principals:
        # Service Principal not found -> Create
        r = session.post("account/scim/v2/ServicePrincipals", json={"displayName": display_name})
        principal = r.json()
        principal_id = principal["applicationId"]
        print_success_or_error(r, f"Create Service Principal: {display_name}")

        # Assign Service Principal to Workspace
        r = session.post(
            "preview/scim/v2/ServicePrincipals",
            json={"applicationId": principal_id},
        )
        print_success_or_error(r, f"Assign Service Principal To Current Workspace: {display_name}")
        return principal

    return service_principals[display_name]


def create_or_update_service_principal_token(session, principal, lifetime="31536000"):
    principal_id = principal["applicationId"]
    # Grant Service Principal permission to USE token
    r = session.patch(
        "permissions/authorization/tokens",
        json={
            "access_control_list": [
                {
                    "service_principal_name": principal_id,
                    "permission_level": "CAN_USE",
                }
            ]
        },
    )
    print_success_or_error(r, f"Grant Service Principal USE Token: {principal_id}")

    # Create Service Principal Token
    if str(r.status_code).startswith("2"):
        r = session.post(
            "token-management/on-behalf-of/tokens",
            json={
                "application_id": principal_id,
                "comment": "Service Principal Token",
                "lifetime_seconds": lifetime,
            },
        )
        print_success_or_error(r, f"Create Service Principal Token: {principal_id}")
    return r.json()


def create_or_update_service_principal_git_token(session, git_username, git_token):
    r = session.get("git-credentials")
    credential = r.json().get("credentials")
    if credential:
        credential_id = credential[0]["credential_id"]
        if credential[0]["git_username"] == git_username:
            r = session.patch(
                f"git-credentials/{credential_id}",
                json={
                    "personal_access_token": git_token,
                    "git_username": git_username,
                    "git_provider": "gitLab",
                },
            )
            print_success_or_error(r, f"Update Service Principal Git Token: {git_username}")
        else:
            print("[ERROR] Username mismatch.")
    else:
        r = session.post(
            "git-credentials",
            json={
                "personal_access_token": git_token,
                "git_username": git_username,
                "git_provider": "gitLab",
            },
        )
        print_success_or_error(r, f"Create Service Principal Git Token: {git_username}")
    return r.json()


def service_principal(session, display_name, git_token, token):
    principal = create_or_get_service_principal(session, display_name)

    if token is None:
        token = create_or_update_service_principal_token(session, principal)
        print(token)
    else:
        token = {"token_value": token}

    sp_session = create_databricks_session(token=token["token_value"], temporary=True)
    response = create_or_update_service_principal_git_token(sp_session, display_name, git_token)

    return response


def housekeep_service_principal(session):
    # Delete folders of ghost Service Principal
    for obj in session.get("workspace/list", json={"path": "/Users"}).json()["objects"]:
        if obj["object_type"] == "DIRECTORY" and bool(
            re.match("/Users/[a-f0-9-]{36}", obj["path"])
        ):
            time.sleep(1)
            r = session.post(
                "workspace/delete",
                json={"path": obj["path"] + "/Trash"},
            )
            time.sleep(1)
            r = session.post("workspace/delete", json={"path": obj["path"]})
            print_success_or_error(r, f"Cleaning Path: {obj['path']}")
