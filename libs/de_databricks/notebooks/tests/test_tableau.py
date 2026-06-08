# Databricks notebook source
import unittest

from de_databricks.common.session import *
from de_databricks.tableau.users_and_groups import *

# COMMAND ----------


def get_users_in_group(session, group_name):
    group_id = session.get(f"groups?filter=name:eq:{group_name}").json()["groups"]["group"][0]["id"]
    users = [
        x["name"]
        for x in session.get(f"groups/{group_id}/users?pageSize=1000")
        .json()["users"]
        .get("user", [])
    ]
    return users


class TestTableau(unittest.TestCase):
    def setUp(self):
        tmp_session = create_databricks_session()
        self.session = create_tableau_session(tmp_session)

    def test_sync_users_group(self):
        group_name = "Test - Group Name"
        try:
            sync_users_group(self.session, "test", group_name, ["gt-test"])
        except Exception as e:
            assert (
                str(e) == f"[ERROR] Group Name: [{group_name}] does not start with Prefix: [test]"
            )
        # Add User
        sync_users_group(self.session, "Test", group_name, ["gt-tanqy", "gt-test"])
        assert get_users_in_group(self.session, group_name) == ["gt-tanqy"]

        # Remove User
        sync_users_group(self.session, "Test", group_name, [])
        assert get_users_in_group(self.session, group_name) == []


test = unittest.main(argv=[""], verbosity=2, exit=False, warnings="ignore")

# COMMAND ----------
