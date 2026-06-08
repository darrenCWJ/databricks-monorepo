import re
from urllib.parse import urljoin

import requests
from databricks.sdk import AccountClient
from databricks.sdk.runtime import dbutils
from pyspark.sql import *
from urllib3.exceptions import InsecureRequestWarning

from de_databricks.common.utils import *

spark = SparkSession.builder.appName("session").getOrCreate()


class CustomSession(requests.Session):
    def __init__(self, url_base=None, verify=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url_base = url_base
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
        }
        self.verify = verify
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

        cur_url = spark.conf.get("spark.databricks.workspaceUrl")
        self.workspace_url = cur_url

        # define default account ID and workspace URLs (optional)
        if cur_url == "dbc-378ee888-e6c8.cloud.databricks.com":
            self.env = "dev"
            self.account_id = "a53813dc-6929-4f14-9c65-c140cc101566"
            self.workspace_id = "6590280815455217"
        elif cur_url == "gvt-databricks-uat.cloud.databricks.com":
            self.env = "uat"
            self.account_id = "a674506f-d79f-4645-908c-da172e7eae9e"
            self.workspace_id = "1948058697086870"
        elif cur_url == "gvt-databricks.cloud.databricks.com":
            self.env = "prd"
            self.account_id = "a674506f-d79f-4645-908c-da172e7eae9e"
            self.workspace_id = "2312200626155212"

    def request(self, method, url, **kwargs):
        modified_url = urljoin(self.url_base, url)
        return super().request(method, modified_url, verify=self.verify, **kwargs)

    def update_api_version(self, version):
        self.url_base = re.sub(r"[0-9]{1,2}\.[0-9]{1,2}", version, self.url_base)

    def update_base_url(self, url):
        self.url_base += url


def create_secret(session, token, token_key, username):
    # Create scope with user's email
    session.post("secrets/scopes/create", json={"scope": username})
    # Create secret
    r = session.post(
        "secrets/put",
        json={"scope": username, "key": token_key, "string_value": token},
    )
    print_success_or_error(r, f"Create Secret: {username} | {token_key}", ["error"])
    return r


def create_databricks_session(api_version="2.0", token="", temporary=False, dbutils=None):
    #######################################################
    ### This function will be deprecated in the future. ###
    ### Use acct_session or workspace_session instead.  ###
    #######################################################

    if not dbutils:
        from databricks.sdk.runtime import dbutils

    username = dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()

    endpoint = f"https://{spark.conf.get('spark.databricks.workspaceUrl')}/api/{api_version}/"
    session = CustomSession(url_base=endpoint)

    is_token = token
    if not is_token:
        token = dbutils.secrets.get(username, "databricks")

    session.headers.update({"Authorization": f"Bearer {token}"})
    if is_token and not temporary:
        create_secret(session, token, "databricks", username)

    return session


def create_databricks_acct_session(
    api_version="2.0", client_id="", client_secret="", account_id=""
):
    print("Instantiating Databricks account session...")

    # if client credentials are not provided, the function must be called from a Databricks cluster
    # it will look for the SP secrets under the username scope
    if not client_id:
        client_id = (
            dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()
        )

    # if this is run by a non-SP, switch to the SP client_id from the user's scope
    if "@" in client_id:
        client_id = dbutils.secrets.get(client_id, "session_oauth_client")

    # get the oauth secret from the SP scope
    if not client_secret:
        client_secret = dbutils.secrets.get(client_id, "session_oauth_secret")

    session = CustomSession()
    if not account_id:
        print("Databricks account ID not defined. Retrieving default Databricks account ID...")
        account_id = session.account_id
        print(f"Databricks account ID: {account_id}")

    # use OAuth credentials to obtain an access token
    url = f"https://accounts.cloud.databricks.com/oidc/accounts/{account_id}/v1/token"
    r = requests.post(
        url,
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        data={"grant_type": "client_credentials", "scope": "all-apis"},
        auth=(client_id, client_secret),
    )
    print(f"OAuth token response: {r.status_code}")

    token = r.json()["access_token"]
    session.url_base = (
        f"https://accounts.cloud.databricks.com/api/{api_version}/accounts/{account_id}/"
    )
    session.headers.update({"Authorization": f"Bearer {token}"})
    print("Databricks account session created successfully")

    return session


def create_databricks_workspace_session(
    api_version="2.0", client_id="", client_secret="", workspace_url=""
):
    print(f"Instantiating Databricks workspace session for {workspace_url}...")

    # if client credentials are not provided, the function must be called from a Databricks cluster
    # it will look for the SP secrets under the username scope
    if not client_id:
        client_id = (
            dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()
        )

    # if this is run by a non-SP, switch to the SP client_id from the user's scope
    if "@" in client_id:
        client_id = dbutils.secrets.get(client_id, "session_oauth_client")

    # get the oauth secret from the SP scope
    if not client_secret:
        client_secret = dbutils.secrets.get(client_id, "session_oauth_secret")

    session = CustomSession()
    if not workspace_url:
        print("Databricks host URL not defined. Retrieving default Databricks host URL...")
        workspace_url = session.workspace_url
        print(f"Databricks host URL: {workspace_url}")

    # use OAuth credentials to obtain an access token
    url = f"https://{workspace_url}/oidc/v1/token"
    r = requests.post(
        url,
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        data={"grant_type": "client_credentials", "scope": "all-apis"},
        auth=(client_id, client_secret),
    )
    print(f"OAuth token response: {r.status_code}")

    token = r.json()["access_token"]
    session.url_base = f"https://{workspace_url}/api/{api_version}/"
    session.headers.update({"Authorization": f"Bearer {token}"})
    print("Databricks workspace session created successfully")

    return session


def create_databricks_acct_sdk(
    account_id=None, client_id=None, client_secret=None, secret_scope="shared_admin_secrets"
):
    """
    Creates a Databricks AccountClient using shared service principal credentials.

    Args:
        account_id: Databricks account ID (optional, will fetch from secrets if not provided)
        client_id: OAuth client ID (optional, will fetch from secrets if not provided)
        client_secret: OAuth client secret (optional, will fetch from secrets if not provided)
        secret_scope: Secret scope name containing shared credentials

    Returns:
        AccountClient: Configured Databricks account client

    Raises:
        ValueError: If required parameters are missing or invalid
        RuntimeError: If secret retrieval fails or client creation fails
    """

    try:
        # Retrieve account_id
        if not account_id:
            try:
                account_id = dbutils.secrets.get(secret_scope, "databricks_account_id")
            except Exception as e:
                raise RuntimeError(
                    f"Failed to retrieve account ID from secret scope '{secret_scope}': {str(e)}"
                )

        # Validate account_id format (basic UUID validation)
        if not account_id or len(account_id.strip()) == 0:
            raise ValueError("Account ID cannot be empty")

        # Retrieve credentials if not provided
        if not client_id or not client_secret:
            try:
                if not client_id:
                    client_id = dbutils.secrets.get(secret_scope, "databricks_oauth_client_id")
                if not client_secret:
                    client_secret = dbutils.secrets.get(
                        secret_scope, "databricks_oauth_client_secret"
                    )
            except Exception as e:
                raise RuntimeError(
                    f"Failed to retrieve OAuth credentials from secret scope '{secret_scope}': {str(e)}"
                )

        # Validate credentials
        if not client_id or len(client_id.strip()) == 0:
            raise ValueError("Client ID cannot be empty")
        if not client_secret or len(client_secret.strip()) == 0:
            raise ValueError("Client secret cannot be empty")

        # Create AccountClient
        try:
            account_client = AccountClient(
                host="https://accounts.cloud.databricks.com",
                account_id=account_id.strip(),
                client_id=client_id.strip(),
                client_secret=client_secret.strip(),
            )
            return account_client

        except Exception as e:
            raise RuntimeError(f"Failed to create Databricks AccountClient: {str(e)}")

    except (ValueError, RuntimeError):
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        # Catch any unexpected exceptions
        raise RuntimeError(f"Unexpected error creating Databricks account session: {str(e)}")


def create_tableau_session(session, api_version="3.19", token=""):

    # Session and Username to get DataBricks Secret
    username = dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()
    token_key = "tableau"

    if spark.conf.get("spark.databricks.workspaceUrl").startswith("gvt-databricks."):
        endpoint = f"https://tableau.data.tech.gov.sg/api/{api_version}/"
        tb_session = CustomSession(url_base=endpoint)
    else:
        endpoint = f"https://tableauuat.data.tech.gov.sg/api/{api_version}/"
        tb_session = CustomSession(url_base=endpoint, verify=False)

    if not token:
        token = dbutils.secrets.get(username, token_key)
    else:
        create_secret(session, token, token_key, username)

    payload = {
        "credentials": {
            "personalAccessTokenName": "databricks",
            "personalAccessTokenSecret": token,
            "site": {"contentUrl": ""},
        }
    }

    r = tb_session.post("auth/signin", json=payload)
    tb_session.headers.update({"X-tableau-auth": r.json().get("credentials", {}).get("token", "")})
    print_success_or_error(r, "Tableau Sign In", ["error"])
    site_id = r.json()["credentials"]["site"]["id"]
    tb_session.update_base_url(f"sites/{site_id}/")

    return tb_session
