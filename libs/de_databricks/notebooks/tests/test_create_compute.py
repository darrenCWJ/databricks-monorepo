# Databricks notebook source
import unittest

from de_databricks.common.session import *
from de_databricks.compute.shared_compute import *


class TestCreateCompute(unittest.TestCase):
    def setUp(self):
        self.session = create_databricks_session()

    def test_create_shared_cluster(self):
        response = create_shared_cluster(self.session, PROJECT="test")
        assert response.status_code == 200

    def test_permissions(self):
        response = set_cluster_permissions(self.session, PROJECT="test", ENV="uat")
        assert response.status_code == 200


test = unittest.main(argv=[""], verbosity=2, exit=False, warnings="ignore")

# COMMAND ----------
