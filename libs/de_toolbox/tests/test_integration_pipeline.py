"""Integration tests requiring a live Databricks/Spark connection.

Ported from: test_autoloader.py, test_data_vault.py, test_kimball*.py,
             test_data_quality.py, test_ge.py, test_data_profiling.py,
             test_sharepoint_online.py

These tests CANNOT run locally — they require Unity Catalog tables and
a Databricks cluster. Run via: make test P=libs/de_toolbox -m integration
"""

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def env():
    return "dev"


class TestAutoloader:
    """Requires: test_dev.bronze.unit_test table."""

    def test_create_bronze(self, spark, env):
        from de_toolbox._legacy.autoloader_v1 import create_bronze

        create_bronze(spark, "toolbox", "unit_test", env, False, False, None)
        df = spark.read.table("test_dev.bronze.unit_test")
        assert df.count() > 1

    def test_load_dts_not_null(self, spark):
        df = spark.read.table("test_dev.bronze.unit_test")
        for row in df.collect():
            assert row._LOAD_DTS is not None

    def test_column_names_clean(self, spark):
        df = spark.read.table("test_dev.bronze.unit_test")
        system_cols = {"_rescued_data", "_INGEST_DTS", "_LOAD_DTS"}
        for col_name in df.columns:
            if col_name not in system_cols:
                assert col_name.isalnum(), f"Column {col_name} has special chars"


class TestDataVault:
    """Requires: test_dev.silver hub/sat tables."""

    def test_create_silver(self, spark, env):
        from de_toolbox._legacy.data_vault_v1 import create_silver

        create_silver(spark, "toolbox", "unit_test", env, "True", "False", None)
        create_silver(spark, "toolbox", "unit_test", env, "False", "False", None)

    def test_create_silver_output(self, spark):
        assert spark.read.table("test_dev.silver.hub_organization").count() == 3
        assert spark.read.table("test_dev.silver.hub_worker").count() == 4
        assert spark.read.table("test_dev.silver.sat_worker_details_i").count() >= 4
        assert spark.read.table("test_dev.silver.sat_worker_details_ii").count() >= 4


class TestKimball:
    """Requires: test_dev.gold dim/fact tables."""

    def test_create_model(self, spark, env):
        from de_toolbox._legacy.kimball_v1 import create_gold

        create_gold(spark, "toolbox", "unit_test", env, None)
        assert spark.read.table("test_dev.gold.dim_worker").count() > 1
        assert spark.read.table("test_dev.gold.fact_worker_supervisory_org").count() > 1

    def test_scd2_columns_exist(self, spark):
        df_dim = spark.read.table("test_dev.gold.dim_worker")
        col_types = dict(df_dim.dtypes)
        assert col_types.get("_VALID_TO") == "timestamp"
        assert col_types.get("_VALID_FROM") == "timestamp"

    def test_scd1_columns_exist(self, spark):
        df_fact = spark.read.table("test_dev.gold.fact_worker_supervisory_org")
        col_types = dict(df_fact.dtypes)
        assert col_types.get("_LOAD_DTS") == "timestamp"


class TestDataQuality:
    """Requires: databricks_dq_<env>.<project> tables."""

    def test_create_resources(self, spark, env):
        from de_toolbox.quality.checks import dq_checks

        dq_checks(spark, "unit_test", "toolbox", env)
        assert spark.read.table(f"databricks_dq_{env}.toolbox.unit_test_lvl2")

    def test_dq_columns(self, spark, env):
        df = spark.read.table(f"databricks_dq_{env}.toolbox.unit_test_lvl2")
        expected_columns = {
            "EmployeeId",
            "Source",
            "Domain",
            "Subdomain",
            "DataElement",
            "Flag",
            "last_refreshed",
        }
        assert expected_columns.issubset(set(df.columns))

    def test_dq_dimensions(self, spark, env):
        df = spark.read.table(f"databricks_dq_{env}.toolbox.unit_test_lvl2")
        dimensions = {row.Dimension for row in df.select("Dimension").distinct().collect()}
        expected = {"Completeness", "Validity", "Conformity", "Uniqueness"}
        assert dimensions == expected


class TestGreatExpectations:
    """Requires: databricks_dq_<env>.<project> tables + GE."""

    def test_create_resources(self, spark, env):
        from de_toolbox.quality.great_expectations import main

        main("ge_unit_test", "toolbox", env, "no")
        assert spark.read.table(f"databricks_dq_{env}.toolbox.unit_test_ge")

    def test_dq_columns(self, spark, env):
        df = spark.read.table(f"databricks_dq_{env}.toolbox.unit_test_ge")
        expected = {
            "Domain",
            "Sub-Domain",
            "Table",
            "Column_Name",
            "Dimension",
            "Success_Rate",
            "Last_Refreshed_Date",
        }
        assert expected.issubset(set(df.columns))
