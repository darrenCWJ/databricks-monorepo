# Databricks notebook source
import unittest

from de_databricks.common.session import *

# COMMAND ----------


class TestCommonSession(unittest.TestCase):
    def setUp(self):
        self.session = create_databricks_session()

    def test_create_session(self):
        assert self.session.headers["Authorization"].startswith("Bearer")

        rogue_session = create_databricks_session(token="HelloWorld", temporary=True)
        assert "Invalid access token" in rogue_session.get("preview/scim/v2/Me").text

        tableau_session = create_tableau_session(session, "UAT", token="")
        assert len(tableau_session.headers["X-tableau-auth"]) == 92

    def test_create_session(self):
        response = create_secret(self.session, "Test", "Test", "Test")
        assert response.status_code == 200


test = unittest.main(argv=[""], verbosity=2, exit=False, warnings="ignore")

# COMMAND ----------
