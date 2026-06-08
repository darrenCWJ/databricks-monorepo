"""Tests for de_toolbox.catalog — ported from test_common_function.py."""

import pytest
from de_toolbox.catalog import get_catalog, get_repo_path


class TestGetCatalog:
    def test_valid_environments(self):
        assert get_catalog("project1", "dev") == "project1_dev"
        assert get_catalog("project2", "uat") == "project2_uat"
        assert get_catalog("project3", "stg") == "project3_stg"
        assert get_catalog("project4", "prd") == "project4_prd"

    def test_invalid_environment(self):
        with pytest.raises(ValueError, match="Catalog Env: invalid is invalid\!"):
            get_catalog("project", "invalid")

    def test_case_sensitivity(self):
        with pytest.raises(ValueError):
            get_catalog("project", "DEV")

    def test_empty_strings(self):
        assert get_catalog("", "dev") == "_dev"
        with pytest.raises(ValueError):
            get_catalog("project", "")

    def test_special_characters(self):
        assert get_catalog("project\!@#", "dev") == "project\!@#_dev"


class TestGetRepoPath:
    def test_with_debug(self):
        assert get_repo_path("project1", "debug_folder") == (
            "/Workspace/Repos/debug_folder/de_project1/metadata/base"
        )
        assert get_repo_path("project2", "another_debug", "custom") == (
            "/Workspace/Repos/another_debug/de_project2/metadata/custom"
        )

    def test_toolbox_project(self):
        assert get_repo_path("toolbox", None) == (
            "/Workspace/Repos/shared/de_toolbox/metadata/base"
        )
        assert get_repo_path("toolbox", None, "custom") == (
            "/Workspace/Repos/shared/de_toolbox/metadata/custom"
        )

    def test_default_case(self):
        assert get_repo_path("project1", None) == "../metadata/base"
        assert get_repo_path("project2", None, "custom") == "../metadata/custom"

    def test_debug_precedence(self):
        assert get_repo_path("toolbox", "debug_folder") == (
            "/Workspace/Repos/debug_folder/de_toolbox/metadata/base"
        )

    def test_special_characters(self):
        assert get_repo_path("project\!@#", "debug$%^", "folder&*()") == (
            "/Workspace/Repos/debug$%^/de_project\!@#/metadata/folder&*()"
        )
