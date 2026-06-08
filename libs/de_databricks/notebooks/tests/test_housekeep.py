# Databricks notebook source
import unittest

from pyspark.testing import assertDataFrameEqual

# COMMAND ----------

# MAGIC %run ../housekeep/main

# COMMAND ----------


class TestHousekeep(unittest.TestCase):
    def setUp(self):
        self.test_df = spark.createDataFrame(
            [
                ("admin_sandbox", "billing", datetime.now()),
                ("admin_sandbox", "column", datetime.now()),
            ],
            ["catalog_name", "schema_name", "schema_updated_at"],
        )

    def test_get_table_or_volume_info(self):
        test_columns = ["asset_type", "catalog_name", "name", "schema_name"]
        test_df = get_table_or_volume_info(self.test_df, "tables").select(test_columns)
        expected_df = spark.createDataFrame(
            [
                ("tables", "admin_sandbox", "list_prices", "billing"),
                ("tables", "admin_sandbox", "usage", "billing"),
                ("tables", "admin_sandbox", "test", "column"),
            ],
            test_columns,
        )
        assertDataFrameEqual(test_df, expected_df)

    def test_get_catalog_and_schema_info(self):
        test_df = get_catalog_and_schema_info(3)
        assert test_df.count() > 0

    def test_housekeep_catalog(self):
        test_df = housekeep_catalog()
        assert (
            len(
                set(test_df.select("asset_type").distinct().toPandas()["asset_type"])
                - set([None, "tables", "volumes"])
            )
            == 0
        )
        assert (
            datetime.now().date() - test_df.select(to_date(max("updated_at"))).collect()[0][0]
        ).days > 90

    def test_get_all_users(self):
        test_df = get_all_users()
        assert test_df.count() > 100
        assertDataFrameEqual(test_df.select("email"), test_df.select(lower("email").alias("email")))

    def test_get_active_users(self):
        test_df = get_active_users()
        assert test_df.count() > 20
        assert (
            datetime.now().date() - test_df.select(to_date(min("event_date"))).collect()[0][0]
        ).days <= 90
        assertDataFrameEqual(test_df.select("email"), test_df.select(lower("email").alias("email")))

    def test_delete_users(self):
        all_users_df = get_all_users()
        active_users_df = get_active_users()
        test_df = delete_users(all_users_df, active_users_df)
        expected_df = spark.sql("SELECT lower(current_user()) AS email")
        assert test_df.join(expected_df, "email").count() == 0


# COMMAND ----------

unittest.main(argv=[""], exit=False, warnings="ignore", verbosity=2)

# COMMAND ----------
