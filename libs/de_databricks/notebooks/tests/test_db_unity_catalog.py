# Databricks notebook source
import unittest
from pprint import pprint

from de_databricks.common.session import *
from de_databricks.common.utils import is_valid_email
from de_databricks.unitycatalog.db_unity_catalog_grants import *

# COMMAND ----------


### This test the getting permission, getting effective permission and also updating permission of unity catalog securable object.
class TestUsersGroup(unittest.TestCase):
    def setUp(self):
        self.session = create_databricks_session()
        self.session.update_api_version("2.1")

    def test_01_validate_group_name(self):
        response = is_valid_email("demo@testing.gov.sg")
        assert response == True

    def test_02_get_permissions(self):
        securable_name = "admin_uat"
        securable_type = "catalog"
        response = get_permissions(self.session, securable_type, securable_name)
        assert len(response["privilege_assignments"]) > 0
        assert response["privilege_assignments"][0]["principal"]

    def test_02_get_effective_permissions(self):
        securable_name = "admin_uat"
        securable_type = "catalog"
        response = get_effective_permissions(self.session, securable_type, securable_name)
        assert len(response["privilege_assignments"]) > 0
        assert response["privilege_assignments"][0]["principal"]

    def test_03_update_permissions_add(self):
        securable_name = "test_uat.autoloader.unit_test"
        securable_type = "table"
        operation = "add"
        permissions = ["SELECT"]
        principle = "uat_test_owners"
        response = update_permissions(
            self.session, securable_type, securable_name, operation, permissions, principle
        )
        assert len(response["privilege_assignments"]) > 0
        assert response["privilege_assignments"][0]["principal"] == "uat_test_owners"
        assert response["privilege_assignments"][0]["privileges"] == ["SELECT"]

    def test_04_update_permissions_remove(self):
        securable_name = "test_uat.autoloader.unit_test"
        securable_type = "table"
        operation = "remove"
        permissions = ["SELECT"]
        principle = "uat_test_owners"
        response = update_permissions(
            self.session, securable_type, securable_name, operation, permissions, principle
        )
        assert type(response) == dict


test = unittest.main(argv=[""], verbosity=2, exit=False, warnings="ignore")

# COMMAND ----------
