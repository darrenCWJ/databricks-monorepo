# Databricks notebook source
import unittest
from pprint import pprint

from de_databricks.common.session import *
from de_databricks.workflow.job import *

# COMMAND ----------


class TestWorkflowJob(unittest.TestCase):
    def setUp(self):
        self.config = "workflow/toolbox.json"
        self.cluster_id = "0801-044744-oa6ze1ky"
        self.git_url = "https://sgts.gitlab-dedicated.com/wog/gvt/dart/gvt-dsaid-dart/databricks/de_toolbox.git"
        self.session = create_databricks_session()
        self.target_schema = ["bronze", "silver", "gold", "mart"]

        org_id = spark.conf.get("spark.databricks.clusterUsageTags.clusterOwnerOrgId")
        self.is_prd = org_id.endswith("5212")
        self.project = "test2"

    def test_create_or_update_job(self):
        # UAT Pipeline
        response = create_or_update_job(
            self.session,
            config=self.config,
            CLUSTER_ID=self.cluster_id,
            ENV="uat",
            GIT_BRANCH="dev",
            GIT_URL=self.git_url,
            PROJECT="test",
        )
        assert response.status_code == 200

        # UAT Pipeline (Hard Reset + Debug)
        response = create_or_update_job(
            self.session,
            config=self.config,
            hard_reset=True,
            debug=True,
            CLUSTER_ID=self.cluster_id,
            ENV="uat",
            GIT_BRANCH="dev",
            GIT_URL=self.git_url,
            PROJECT="test",
        )
        assert response.status_code == 200

    def test_format_and_autofill_config(self):
        # PRD Config
        config = format_and_autofill_config(
            self.session,
            config=self.config,
            name="test",
            CLUSTER_ID=self.cluster_id,
            ENV="prd",
            GIT_BRANCH="main",
            GIT_URL=self.git_url,
        )
        assert config["git_source"]["git_branch"] == "main"
        assert config["run_as"]["service_principal_name"] == "8ac61dd5-8c6e-47ad-97c5-1468ccbdce19"
        assert config["name"] == "test"

        # PRD Config (Debug)
        config = format_and_autofill_config(
            self.session,
            config=self.config,
            name="test",
            debug=True,
            CLUSTER_ID=self.cluster_id,
            ENV="prd",
            GIT_BRANCH="stg",
            GIT_URL=self.git_url,
        )

        assert config["git_source"]["git_branch"] == "stg"
        assert "run_as" not in config
        assert config["tasks"][0]["existing_cluster_id"] == self.cluster_id

    def test_create_trigger_once_job(self):
        # Check if workflow is successful
        response = create_trigger_once_job(
            self.session,
            config="workflow/onboarding_unit_test.json",
            CLUSTER_ID="0801-044744-oa6ze1ky",
            ENV="uat",
            GIT_BRANCH="f_onboarding_workflow",
            GIT_URL="https://sgts.gitlab-dedicated.com/wog/gvt/dart/gvt-dsaid-dart/databricks/de_databricks.git",
            PROJECT=self.project,
        )
        assert response.status_code == 200

    def test_create_shared_cluster_and_permissions(self):
        # Check if shared cluster is created
        session = self.session
        project = self.project

        cluster_list = session.get("clusters/list")

        cluster_dic = {}
        res_json = json.loads(cluster_list.text)
        for k in res_json["clusters"]:
            if k["cluster_name"] == f"{project.upper()}'s Cluster":
                cluster_dic[k["cluster_id"]] = k["cluster_name"]

        assert len(cluster_dic) == 1
        assert list(cluster_dic.values())[0] == f"{project.upper()}'s Cluster"

        if len(cluster_dic) == 1:
            cluster_id = list(cluster_dic.keys())[0]
            permissions = session.get(f"permissions/clusters/{cluster_id}")
            permissions_dic = {}
            permissions_json = json.loads(permissions.text)
            for k in permissions_json["access_control_list"]:
                for i in k["all_permissions"]:
                    permissions_dic[k["group_name"]] = i["permission_level"]

            if self.is_prd:
                self.assertDictEqual(
                    permission_dic,
                    {
                        "admins": "CAN_MANAGE",
                        "prd_test2_owners": "CAN_RESTART",
                        "prd_test2_ba": "CAN_RESTART",
                    },
                )
            else:
                self.assertDictEqual(
                    permission_dic,
                    {
                        "admins": "CAN_MANAGE",
                        "uat_test2_owners": "CAN_RESTART",
                        "uat_test2_ba": "CAN_RESTART",
                    },
                )

    def test_create_catalogs_and_volumes(self):
        env = "prd" if self.is_prd else "uat"
        project = self.project

        # Check if catalog is created
        catalogs = spark.sql("SHOW CATALOGS").toPandas().catalog
        for catalog in catalogs:
            if catalog == f"{project}_{env}":
                catalog_created = catalog
            else:
                None

        # Check if schema is created
        schemas = spark.sql(f"SHOW SCHEMAS IN {project}_{env}").toPandas().databaseName
        schema_list = []
        target_schema = self.target_schema
        for schema in schemas:
            if schema in target_schema:
                schema_list.append(schema)

        # Check if volume is created
        volumes = spark.sql(f"SHOW VOLUMES IN {project}_{env}.bronze").toPandas().volume_name
        volume_list = []
        for volume in volumes:
            if volume in ["test1", "test2"]:
                volume_list.append(volume)

        assert catalog_created == f"{project}_{env}"
        self.assertEqual(sorted(schema_list), sorted(target_schema))
        self.assertEqual(sorted(volume_list), sorted(["test1", "test2"]))

    def test_resources_owner(self):
        env = "prd" if self.is_prd else "uat"
        project = self.project

        # Check if resources created are owned by respective owner -- CATALOG
        catalog_owner = spark.sql(f"DESCRIBE CATALOG {project}_{env}").toPandas().info_value[2]
        catalog_res = True if catalog_owner.endswith(f"{env}_{project}_owners") else False

        self.assertTrue(
            catalog_res,
            f"Catalog owner is not owned by respective owners. It is owned by {catalog_owner}",
        )

        # Check if resources created are owned by respective owner -- SCHEMAS
        target_schema = self.target_schema
        for schema in target_schema:
            schema_owner = (
                spark.sql(f"DESCRIBE SCHEMA {project}_{env}.{schema}")
                .toPandas()
                .database_description_value[4]
            )
            schema_res = True if schema_owner.endswith(f"{env}_{project}_owners") else False

            self.assertTrue(
                schema_res,
                f"{schema} schema owner is not owned by respective owners. It is owned by {schema_owner}",
            )

        # Check if resources created are owned by respective owner -- VOLUMES
        for volume in ["test1", "test2"]:
            volume_owner = (
                spark.sql(f"DESCRIBE VOLUME {project}_{env}.bronze.{volume}").toPandas().owner[0]
            )
            volume_res = True if volume_owner.endswith(f"{env}_{project}_owners") else False

            self.assertTrue(
                volume_res,
                f"{volume} volume owner is not owned by respective owners. It is owned by {volume_owner}",
            )


test = unittest.main(argv=[""], verbosity=2, exit=False, warnings="ignore")

# COMMAND ----------
