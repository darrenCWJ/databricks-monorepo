"""Authentication utilities for external APIs.

Pure Python — no spark or dbutils dependency.
"""

import json
import time
from base64 import b64decode

import jwt
import requests
from cryptography.hazmat.primitives import serialization


def get_wd_token(client_id: str, user_id: str, private_key: str, api_url: str) -> str:
    """Generate a Workday access token using JWT assertion.

    Args:
        client_id: OAuth client ID (ISU).
        user_id: Workday user ID (subject).
        private_key: Base64-encoded DER private key.
        api_url: Workday token endpoint URL.

    Returns:
        Access token string.

    Raises:
        Exception: If token request returns non-200 status.
    """
    payload = {
        "iss": client_id,
        "sub": user_id,
        "aud": "wd",
        "exp": str(round(time.time()) + 300),
    }

    key_der = b64decode(private_key)
    key_pem = serialization.load_der_private_key(key_der, password=None).private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    encoded_jwt = jwt.encode(payload, key_pem, algorithm="RS256")

    form_data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": encoded_jwt,
    }

    response = requests.post(api_url, data=form_data, headers={"User-Agent": "GVT CDO"})

    if response.status_code != 200:
        raise Exception(f"Error obtaining token: {response.status_code} {response.text}")

    return json.loads(response.text)["access_token"]
