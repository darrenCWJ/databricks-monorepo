from databricks.sdk import WorkspaceClient
from databricks.sdk.service.iam import ServicePrincipal

from de_databricks.common.session import create_databricks_acct_sdk


def create_or_get_service_principal(display_name: str):
    """
    Create or get a service principal using Databricks SDK

    Args:
        display_name: Display name for the service principal

    Returns:
        ServicePrincipal object
    """

    # Initialize clients within the function
    workspace_client = WorkspaceClient()
    account_client = create_databricks_acct_sdk()

    # Get all service principals from workspace and find by display name
    try:
        service_principals = workspace_client.service_principals.list()

        # Look for existing service principal
        for sp in service_principals:
            if sp.display_name == display_name:
                print(f"Found existing service principal: {display_name}")
                return sp

    except Exception as e:
        print(f"Error listing service principals: {e}")
        return None

    # Service principal not found, create new one
    try:
        # Create service principal at account level first
        new_sp = account_client.service_principals.create(display_name=display_name)

        print(f"Successfully created service principal: {display_name}")

        # Assign to current workspace
        workspace_client.service_principals.create(application_id=new_sp.application_id)

        print(f"Successfully assigned service principal to workspace: {display_name}")

        return new_sp

    except Exception as e:
        print(f"Error creating service principal: {e}")
        return None
