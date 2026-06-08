"""Shared test fixtures for de_toolbox."""

import sys
import types
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Mock external modules unavailable locally (pyspark, databricks SDK,
# requests_ntlm). Registered BEFORE any de_toolbox imports.
# ---------------------------------------------------------------------------


class _AnalysisException(Exception):
    """Fake pyspark AnalysisException for unit testing."""

    def __init__(self, message=""):
        super().__init__(message)
        self.message = message

    def __str__(self):
        return self.message


def _install_mock_modules():
    mock_pyspark = MagicMock()
    mock_pyspark_sql = MagicMock()
    mock_pyspark_sql_functions = MagicMock()
    mock_pyspark_sql_types = MagicMock()
    mock_pyspark_sql_utils = MagicMock()
    mock_pyspark_sql_utils.AnalysisException = _AnalysisException

    mock_pyspark.sql = mock_pyspark_sql
    mock_pyspark.sql.functions = mock_pyspark_sql_functions
    mock_pyspark.sql.types = mock_pyspark_sql_types
    mock_pyspark.sql.utils = mock_pyspark_sql_utils

    mock_databricks = types.ModuleType("databricks")
    mock_databricks_sdk = types.ModuleType("databricks.sdk")
    mock_databricks_sdk_runtime = types.ModuleType("databricks.sdk.runtime")
    mock_databricks_sdk_runtime.spark = MagicMock()
    mock_databricks_sdk_runtime.dbutils = MagicMock()

    mock_databricks.sdk = mock_databricks_sdk
    mock_databricks_sdk.runtime = mock_databricks_sdk_runtime

    mock_requests_ntlm = types.ModuleType("requests_ntlm")
    mock_requests_ntlm.HttpNtlmAuth = MagicMock()

    mock_pyspark_sql_window = MagicMock()
    mock_pyspark_dbutils = MagicMock()

    mock_delta = types.ModuleType("delta")
    mock_delta_tables = MagicMock()
    mock_delta.tables = mock_delta_tables

    mock_jwt = MagicMock()

    mock_crypto = types.ModuleType("Crypto")
    mock_crypto_hash = MagicMock()
    mock_crypto_publickey = MagicMock()
    mock_crypto.Hash = mock_crypto_hash
    mock_crypto.PublicKey = mock_crypto_publickey

    mock_urllib3 = MagicMock()

    mock_account = types.ModuleType("account")
    mock_account_iam = MagicMock()
    mock_account.iam = mock_account_iam

    modules = {
        "pyspark": mock_pyspark,
        "pyspark.sql": mock_pyspark_sql,
        "pyspark.sql.functions": mock_pyspark_sql_functions,
        "pyspark.sql.types": mock_pyspark_sql_types,
        "pyspark.sql.utils": mock_pyspark_sql_utils,
        "pyspark.sql.window": mock_pyspark_sql_window,
        "pyspark.dbutils": mock_pyspark_dbutils,
        "databricks": mock_databricks,
        "databricks.sdk": mock_databricks_sdk,
        "databricks.sdk.runtime": mock_databricks_sdk_runtime,
        "requests_ntlm": mock_requests_ntlm,
        "delta": mock_delta,
        "delta.tables": mock_delta_tables,
        "jwt": mock_jwt,
        "Crypto": mock_crypto,
        "Crypto.Hash": mock_crypto_hash,
        "Crypto.Hash.SHA256": MagicMock(),
        "Crypto.PublicKey": mock_crypto_publickey,
        "Crypto.PublicKey.RSA": MagicMock(),
        "urllib3": mock_urllib3,
        "urllib3._collections": MagicMock(),
        "botocore": MagicMock(),
        "botocore.config": MagicMock(),
        "account": mock_account,
        "account.iam": mock_account_iam,
    }

    for name, mod in modules.items():
        if name not in sys.modules:
            sys.modules[name] = mod


_install_mock_modules()

# ---------------------------------------------------------------------------

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def pipeline_metadata() -> dict:
    with open(FIXTURES_DIR / "unit_test_pipeline.json") as f:
        return json.load(f)


@pytest.fixture
def profiling_metadata() -> dict:
    with open(FIXTURES_DIR / "unit_test_profiling.json") as f:
        return json.load(f)


@pytest.fixture
def profiling_sample_data() -> dict:
    with open(FIXTURES_DIR / "sample_data_profiling.json") as f:
        return json.load(f)


@pytest.fixture
def dq_metadata() -> dict:
    with open(FIXTURES_DIR / "unit_test_dq.json") as f:
        return json.load(f)


@pytest.fixture
def ge_metadata() -> dict:
    with open(FIXTURES_DIR / "unit_test_ge.json") as f:
        return json.load(f)


@pytest.fixture
def gold_metadata() -> dict:
    with open(FIXTURES_DIR / "unit_test_gold.json") as f:
        return json.load(f)
