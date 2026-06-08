"""Minimal local pytest that verifies the package structure imports correctly.

Note: Many modules import pyspark and databricks.sdk which may not be available
locally without a configured Databricks workspace connection. These tests use
try/except to gracefully skip when runtime dependencies are unavailable.
"""

import importlib

import pytest


@pytest.mark.unit
def test_package_exists():
    """Verify the de_databricks package is discoverable."""
    import de_databricks

    assert de_databricks is not None


@pytest.mark.unit
def test_subpackage_structure():
    """Verify all expected subpackages exist as importable modules."""
    expected_modules = [
        "de_databricks.common",
        "de_databricks.account",
        "de_databricks.iam",
        "de_databricks.compute",
        "de_databricks.workflow",
        "de_databricks.unitycatalog",
        "de_databricks.housekeep",
        "de_databricks.tableau",
        "de_databricks.setup",
        "de_databricks.migrate",
    ]
    for module_name in expected_modules:
        spec = importlib.util.find_spec(module_name)
        assert spec is not None, f"Module {module_name} not found"


@pytest.mark.unit
def test_utils_pure_functions():
    """Test pure-Python utilities that don't require Databricks runtime.

    The utils module imports from databricks.sdk.runtime at module level.
    If that import fails (no credentials configured), skip this test.
    """
    try:
        from de_databricks.common.utils import (
            CustomResponse,
            is_valid_email,
            print_success_or_error,
            validate_group_name,
        )
    except (ImportError, ValueError):
        pytest.skip("Databricks runtime not available locally")

    # is_valid_email
    assert is_valid_email("test@example.com") is True
    assert is_valid_email("invalid") is False
    assert is_valid_email("user@domain.co.uk") is True

    # validate_group_name
    assert validate_group_name("UAT_Project_Schema") == "uat_project_schema"
    assert validate_group_name("DEV_Test") == "dev_test"

    # CustomResponse
    resp = CustomResponse(200, "OK")
    assert resp.status_code == 200
    assert resp.text == "OK"

    # print_success_or_error is callable
    assert callable(print_success_or_error)
