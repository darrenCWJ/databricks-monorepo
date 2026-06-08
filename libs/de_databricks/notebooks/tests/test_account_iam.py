# Databricks notebook source
import re
import time
import unittest

from de_databricks.account.iam import *
from de_databricks.common.session import *
from de_databricks.common.utils import print_success_or_error

# COMMAND ----------


class TestAccountIam(unittest.TestCase):
    def setUp(self):
        self.session = create_databricks_session()

    def test_create_or_get_service_principal(self):
        principal = create_or_get_service_principal(self.session, "uat_admin_principal")
        assert principal["displayName"] == "uat_admin_principal"

    def test_create_or_update_service_principal_token(self):
        principal = create_or_get_service_principal(self.session, "uat_admin_principal")
        token = create_or_update_service_principal_token(self.session, principal)
        assert token["token_info"]["comment"] == "Service Principal Token"

    def test_service_principal(self):
        response = service_principal(
            self.session, display_name="uat_admin_principal", git_token="password"
        )

    def tearDown(self):
        return
        housekeep_service_principal(self.session)


test = unittest.main(argv=[""], verbosity=2, exit=False, warnings="ignore")

# COMMAND ----------
