# Databricks notebook source
import unittest
from pprint import pprint

from de_databricks.common.session import *
from de_databricks.common.utils import validate_group_name
from de_databricks.iam.db_group import *

# COMMAND ----------


### This test the group api in account level.
### All account level api need access to the "accounts.cloud.databricks.com" to run
class TestUsersGroup(unittest.TestCase):
    def setUp(self):
        self.session = convert_session_account(create_databricks_session())
        self.session_ws = create_databricks_session()

    def test_00_validate_group_name(self):
        test_string = validate_group_name("UAT_Project_Schema_TableName")
        assert test_string == "uat_project_schema_tablename"

    def test_01_create_user(self):
        env = self.session.env
        if env == "stg" or env == "prd" or env == "uat":
            assert 1 == 1
        else:
            response = create_new_user(self.session, "jeffrey_siew@tech.gov.sg")
            assert response["status"] == "409"

    def test_02_create_new_group(self):
        # Test Create New Group with Members
        response = create_new_group(
            self.session, "uat_unittest_x_grp", ["jeffrey_siew@tech.gov.sg"]
        )
        assert response["schemas"][0] == "urn:ietf:params:scim:schemas:core:2.0:Group"
        assert response["displayName"] == "uat_unittest_x_grp"
        assert response["members"][0]["display"] == "jeffrey_siew@tech.gov.sg"

    def test_03_update_group_members(self):
        # Test Update Group Members
        response = update_group_details_members(
            self.session,
            "uat_unittest_x_grp",
            ["jeffrey_siew@tech.gov.sg", "beatrice_chin@tech.gov.sg"],
            "replace",
        )
        assert response["schemas"][0] == "urn:ietf:params:scim:schemas:core:2.0:Group"
        assert response["displayName"] == "uat_unittest_x_grp"
        assert len(response["members"]) == 2

    def test_04_remove_group_members(self):
        # Test remove group members
        response = update_group_details_members(
            self.session, "uat_unittest_x_grp", ["beatrice_chin@tech.gov.sg"], "remove"
        )
        assert response["schemas"][0] == "urn:ietf:params:scim:schemas:core:2.0:Group"
        assert response["displayName"] == "uat_unittest_x_grp"

    def test_05_add_group_members(self):
        # Test add group members
        response = update_group_details_members(
            self.session, "uat_unittest_x_grp", ["beatrice_chin@tech.gov.sg"], "add"
        )
        assert response["schemas"][0] == "urn:ietf:params:scim:schemas:core:2.0:Group"
        assert response["displayName"] == "uat_unittest_x_grp"
        assert response["members"][0]["value"] == "6477584038851171"

    def test_06_get_group_id(self):
        # Test getting group id number
        response = list_group_details(self.session, "dart_admin")["Resources"][0]["id"]
        assert response == "279762761062948"

    def test_07_get_user_id(self):
        # Test getting user id number
        response = get_user_details(self.session, "jeffrey_siew@tech.gov.sg")["Resources"][0]["id"]
        assert response == "8923042013066107"

    def test_08_assign_group_workspace(self):
        # Test assigning group to workspace
        response = create_update_permissions_assignment(self.session, "uat_unittest_x_grp")
        assert response["principal"]["display_name"] == "uat_unittest_x_grp"

    def test_09_teardown(self):
        # Delete unit test group
        response = delete_group(self.session, "uat_unittest_x_grp")
        assert response.status_code == 204

    def test_11_create_new_group_ws(self):
        # Test Create Group with Members
        response = create_new_group(
            self.session_ws, "uat_unittest_x_grp", ["jeffrey_siew@tech.gov.sg"]
        )
        assert response["meta"]["resourceType"] == "WorkspaceGroup"
        assert response["displayName"] == "uat_unittest_x_grp"
        assert response["members"][0]["display"] == "jeffrey_siew@tech.gov.sg"

    def test_12_update_group_members_ws(self):
        # Test Update Group Members
        response = update_group_details_members(
            self.session_ws,
            "uat_unittest_x_grp",
            ["jeffrey_siew@tech.gov.sg", "beatrice_chin@tech.gov.sg"],
            "replace",
        )
        assert response["meta"]["resourceType"] == "WorkspaceGroup"
        assert response["displayName"] == "uat_unittest_x_grp"
        assert len(response["members"]) == 2

    def test_13_remove_group_members_ws(self):
        # Test remove group members
        response = update_group_details_members(
            self.session_ws, "uat_unittest_x_grp", ["beatrice_chin@tech.gov.sg"], "remove"
        )
        assert response["meta"]["resourceType"] == "WorkspaceGroup"
        assert response["displayName"] == "uat_unittest_x_grp"

    def test_14_add_group_members_ws(self):
        # Test add group members
        response = update_group_details_members(
            self.session_ws, "uat_unittest_x_grp", ["beatrice_chin@tech.gov.sg"], "add"
        )
        assert response["meta"]["resourceType"] == "WorkspaceGroup"
        assert response["displayName"] == "uat_unittest_x_grp"
        assert response["members"][0]["value"] == "6477584038851171"

    def test_15_get_ws_group_id(self):
        # Test getting group id
        response = list_group_details(self.session_ws, "dart_admin")["Resources"][0]["id"]
        assert response == "279762761062948"

    def test_16_get_ws_user_id(self):
        # Test getting user id
        response = get_user_details(self.session_ws, "jeffrey_siew@tech.gov.sg")["Resources"][0][
            "id"
        ]
        assert response == "8923042013066107"

    def test_17_group_workspace_entitlement(self):
        # Test assigning group workspace entitlement
        response = update_group_details_entitlements(
            self.session_ws, "uat_unittest_x_grp", "platform_access"
        )
        assert len(response["entitlements"]) == 2
        assert response["meta"]["resourceType"] == "WorkspaceGroup"
        assert response["displayName"] == "uat_unittest_x_grp"

    def test_18_teardown(self):
        # Delete unit test group
        response = delete_group(self.session_ws, "uat_unittest_x_grp")
        assert response.status_code == 204


test = unittest.main(argv=[""], verbosity=2, exit=False, warnings="ignore")

# COMMAND ----------
