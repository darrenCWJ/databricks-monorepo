"""Tests for de_toolbox.permissions — ported from test_cf_*.py files."""

from unittest.mock import MagicMock, patch

import pytest
from de_toolbox.permissions import (
    change_securable_object_owner,
    grant_securable_object_permission_in_dev,
    set_securable_object_tag,
)
from pyspark.sql.utils import AnalysisException


class TestSetSecurableObjectTag:
    def setup_method(self):
        self.mock_spark = MagicMock()

    def test_set_table_tags(self):
        meta_global = {"tags": {"global_tag": "Global Value"}}
        meta_local = {"tags": {"local_tag": "Local Value", "asset_type": "table"}}
        object_full_path = "catalog.schema.table"

        set_securable_object_tag(self.mock_spark, meta_global, meta_local, object_full_path)

        expected_sql = "ALTER TABLE catalog.schema.table SET TAGS ('global_tag'='global value', 'local_tag'='local value', 'asset_type'='table')"
        self.mock_spark.sql.assert_called_once_with(expected_sql)

    def test_set_volume_tags(self):
        meta_global = {"tags": {"global_tag": "Global Value"}}
        meta_local = {"tags": {"local_tag": "Local Value", "asset_type": "volume"}}
        object_full_path = "catalog.schema.volume"

        set_securable_object_tag(self.mock_spark, meta_global, meta_local, object_full_path)

        expected_sql = "ALTER VOLUME catalog.schema.volume SET TAGS ('global_tag'='global value', 'local_tag'='local value', 'asset_type'='volume')"
        self.mock_spark.sql.assert_called_once_with(expected_sql)

    def test_no_tags(self):
        meta_global = {}
        meta_local = {}
        object_full_path = "catalog.schema.table"

        with patch("builtins.print") as mock_print:
            set_securable_object_tag(self.mock_spark, meta_global, meta_local, object_full_path)

        mock_print.assert_called_once_with("No tags to set for catalog.schema.table in config")
        self.mock_spark.sql.assert_not_called()

    def test_invalid_asset_type(self):
        meta_global = {"tags": {"global_tag": "Global Value"}}
        meta_local = {"tags": {"local_tag": "Local Value", "asset_type": "invalid_type"}}
        object_full_path = "catalog.schema.table"

        with pytest.raises(ValueError, match="asset_type must be one of"):
            set_securable_object_tag(self.mock_spark, meta_global, meta_local, object_full_path)

    def test_sql_exception(self):
        meta_global = {"tags": {"global_tag": "Global Value"}}
        meta_local = {"tags": {"local_tag": "Local Value", "asset_type": "table"}}
        object_full_path = "catalog.schema.table"
        self.mock_spark.sql.side_effect = AnalysisException("SQL Error")

        with patch("builtins.print") as mock_print:
            set_securable_object_tag(self.mock_spark, meta_global, meta_local, object_full_path)

        mock_print.assert_called_once_with(
            "Error setting tags for table catalog.schema.table: SQL Error"
        )

    def test_local_tags_override_global_tags(self):
        meta_global = {"tags": {"common_tag": "Global Value", "global_tag": "Global Value"}}
        meta_local = {
            "tags": {"common_tag": "Local Value", "local_tag": "Local Value", "asset_type": "table"}
        }
        object_full_path = "catalog.schema.table"

        set_securable_object_tag(self.mock_spark, meta_global, meta_local, object_full_path)

        expected_sql = "ALTER TABLE catalog.schema.table SET TAGS ('common_tag'='local value', 'global_tag'='global value', 'local_tag'='local value', 'asset_type'='table')"
        self.mock_spark.sql.assert_called_once_with(expected_sql)

    def test_missing_asset_type(self):
        meta_global = {"tags": {"global_tag": "Global Value"}}
        meta_local = {"tags": {"local_tag": "Local Value"}}
        object_full_path = "catalog.schema.table"

        with pytest.raises(AttributeError):
            set_securable_object_tag(self.mock_spark, meta_global, meta_local, object_full_path)


class TestChangeSecurableObjectOwner:
    @patch("de_toolbox.permissions.format_object_principal")
    def test_set_table_owner(self, mock_format):
        mock_spark = MagicMock()
        mock_meta_global = {"principal_owner": "${project}_${env}_owner"}
        mock_meta_local = {"tags": {"asset_type": "table"}}
        mock_format.return_value = "test_project_dev_owner"

        change_securable_object_owner(
            mock_spark,
            mock_meta_global,
            mock_meta_local,
            "test_project",
            "dev",
            "catalog.schema.table",
        )

        mock_spark.sql.assert_called_once_with(
            "ALTER TABLE catalog.schema.table SET OWNER TO test_project_dev_owner"
        )

    @patch("de_toolbox.permissions.format_object_principal")
    def test_set_volume_owner(self, mock_format):
        mock_spark = MagicMock()
        mock_meta_global = {"principal_owner": "${project}_${env}_owner"}
        mock_meta_local = {"tags": {"asset_type": "volume"}}
        mock_format.return_value = "test_project_dev_owner"

        change_securable_object_owner(
            mock_spark,
            mock_meta_global,
            mock_meta_local,
            "test_project",
            "dev",
            "catalog.schema.volume",
        )

        mock_spark.sql.assert_called_once_with(
            "ALTER VOLUME catalog.schema.volume SET OWNER TO test_project_dev_owner"
        )

    def test_no_principal_owner(self):
        mock_spark = MagicMock()
        mock_meta_global = {}
        mock_meta_local = {"tags": {"asset_type": "table"}}

        with patch("builtins.print") as mock_print:
            change_securable_object_owner(
                mock_spark,
                mock_meta_global,
                mock_meta_local,
                "test_project",
                "dev",
                "catalog.schema.table",
            )

        mock_print.assert_called_once_with(
            "No principal owner to set for catalog.schema.table in config"
        )
        mock_spark.sql.assert_not_called()

    @patch("de_toolbox.permissions.format_object_principal")
    def test_invalid_principal_format(self, mock_format):
        mock_spark = MagicMock()
        mock_meta_global = {"principal_owner": "invalid_owner"}
        mock_meta_local = {"tags": {"asset_type": "table"}}
        mock_format.side_effect = ValueError(
            'Invalid template format: invalid_owner. Principal group name template should contain "${project}" and "${env}".'
        )

        with pytest.raises(ValueError, match="Invalid template format"):
            change_securable_object_owner(
                mock_spark,
                mock_meta_global,
                mock_meta_local,
                "test_project",
                "dev",
                "catalog.schema.table",
            )

    @patch("de_toolbox.permissions.format_object_principal")
    def test_invalid_asset_type(self, mock_format):
        mock_spark = MagicMock()
        mock_meta_global = {"principal_owner": "${project}_${env}_owner"}
        mock_meta_local = {"tags": {"asset_type": "invalid_type"}}
        mock_format.return_value = "test_project_dev_owner"

        with pytest.raises(ValueError, match="asset_type must be one of"):
            change_securable_object_owner(
                mock_spark,
                mock_meta_global,
                mock_meta_local,
                "test_project",
                "dev",
                "catalog.schema.table",
            )

    @patch("de_toolbox.permissions.format_object_principal")
    def test_sql_exception(self, mock_format):
        mock_spark = MagicMock()
        mock_spark.sql.side_effect = AnalysisException("SQL Error")
        mock_meta_global = {"principal_owner": "${project}_${env}_owner"}
        mock_meta_local = {"tags": {"asset_type": "table"}}
        mock_format.return_value = "test_project_dev_owner"

        with patch("builtins.print") as mock_print:
            change_securable_object_owner(
                mock_spark,
                mock_meta_global,
                mock_meta_local,
                "test_project",
                "dev",
                "catalog.schema.table",
            )

        mock_print.assert_called_once_with(
            "Error setting owner test_project_dev_owner for table catalog.schema.table: SQL Error"
        )


class TestGrantSecurableObjectPermissionInDev:
    @patch("de_toolbox.permissions.format_object_principal")
    @patch("de_toolbox.permissions.get_catalog")
    def test_dev_environment_with_permissions(self, mock_get_catalog, mock_format):
        mock_spark = MagicMock()
        mock_meta_global = {
            "project": "test_project",
            "permission_global": [
                {"principal": "group1", "type": ["SELECT", "MODIFY"]},
                {"principal": "group2", "type": ["SELECT"]},
            ],
        }
        mock_format.side_effect = lambda p, e, proj: f"{p}_{e}"

        grant_securable_object_permission_in_dev(
            mock_spark, mock_meta_global, "test_project", "dev", "catalog.schema.table"
        )

        assert mock_spark.sql.call_count == 3

    @patch("de_toolbox.permissions.format_object_principal")
    @patch("de_toolbox.permissions.get_catalog")
    def test_non_dev_environment(self, mock_get_catalog, mock_format):
        mock_spark = MagicMock()
        mock_meta_global = {"project": "test_project"}

        with patch("builtins.print") as mock_print:
            grant_securable_object_permission_in_dev(
                mock_spark, mock_meta_global, "test_project", "prd", "catalog.schema.table"
            )

        mock_print.assert_called_once()
        mock_spark.sql.assert_not_called()

    @patch("de_toolbox.permissions.format_object_principal")
    @patch("de_toolbox.permissions.get_catalog")
    def test_dev_environment_no_permissions(self, mock_get_catalog, mock_format):
        mock_spark = MagicMock()
        mock_meta_global = {"project": "test_project"}

        with patch("builtins.print") as mock_print:
            grant_securable_object_permission_in_dev(
                mock_spark, mock_meta_global, "test_project", "dev", "catalog.schema.table"
            )

        mock_print.assert_called_once_with(
            "No permission to grant for catalog.schema.table in config"
        )
        mock_spark.sql.assert_not_called()

    @patch("de_toolbox.permissions.format_object_principal")
    @patch("de_toolbox.permissions.get_catalog")
    def test_dev_environment_sql_exception(self, mock_get_catalog, mock_format):
        mock_spark = MagicMock()
        mock_spark.sql.side_effect = AnalysisException("SQL Error")
        mock_meta_global = {
            "project": "test_project",
            "permission_global": [{"principal": "group1", "type": ["SELECT"]}],
        }
        mock_format.return_value = "group1_dev"

        with patch("builtins.print") as mock_print:
            grant_securable_object_permission_in_dev(
                mock_spark, mock_meta_global, "test_project", "dev", "catalog.schema.table"
            )

        mock_print.assert_called_once()
