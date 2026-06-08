import ast
import json
import re
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.runtime import *
from databricks.sdk.service.jobs import *

from de_databricks.account.iam_sdk import create_or_get_service_principal
from de_databricks.common.utils import *


def create_trigger_once_job(config, debug=False, **kwargs):
    # Initialize clients within the function
    workspace_client = WorkspaceClient()

    # Reading from file
    data = json.load(open(config))
    name = data["run_name"]

    # Read as String for Find & Replace
    config = open(config).read()

    # Autofill Kwargs
    for k, v in kwargs.items():
        config = config.replace("{{ " + k + " }}", v)

    config = ast.literal_eval(config)

    # Create Pipeline
    response = workspace_client.jobs.submit_run(**config)
    print(f"[SUCCESS] Triggered One Time Pipeline: {name}")
    return response


def create_or_update_job(config, hard_reset=False, debug=False, **kwargs):
    # Initialize clients within the function
    workspace_client = WorkspaceClient()

    # Standardise Pipeline Name
    name = Path(config).stem
    name = (
        f"{kwargs['PROJECT']}-"
        + re.sub(r"[^A-Za-z0-9\n]", "-", name)
        + f"-pipeline-{kwargs['ENV']}"
    )

    # List jobs to find existing job
    try:
        jobs_list = list(workspace_client.jobs.list(name=name, limit=1))
        print("[SUCCESS] List Pipeline")
    except Exception as e:
        print(f"[ERROR] List Pipeline: {e}")
        raise

    config_dict = format_and_autofill_config(config, name, debug, **kwargs)

    # Check if job exists
    job_id = None
    for job in jobs_list:
        if name == job.settings.name:
            job_id = job.job_id
            break

    if job_id:
        # Hard Reset for Config not supported by update
        if hard_reset:
            try:
                workspace_client.jobs.delete(job_id=job_id)
                print(f"[SUCCESS] Delete Pipeline: {name}")
            except Exception as e:
                print(f"[ERROR] Delete Pipeline: {name} - {e}")
                raise
        # Reset job configuration (replaces entire job settings)
        else:
            try:
                # Convert dict to JobSettings object
                job_settings = JobSettings.from_dict(config_dict)
                response = workspace_client.jobs.reset(job_id=job_id, new_settings=job_settings)
                print(f"[SUCCESS] Reset Pipeline: {name}")
                return response
            except Exception as e:
                print(f"[ERROR] Reset Pipeline: {name} - {e}")
                raise

    # Create New Pipeline
    try:
        # Convert dict to JobSettings object for create as well
        response = workspace_client.jobs.create(name=name)
        print(f"[SUCCESS] Create Pipeline: {name}")

        # List jobs to find existing job
        try:
            jobs_list = list(workspace_client.jobs.list(name=name, limit=1))
            print("[SUCCESS] List Pipeline")
        except Exception as e:
            print(f"[ERROR] List Pipeline: {e}")
            raise

        config_dict = format_and_autofill_config(config, name, debug, **kwargs)

        # Check if job exists
        job_id = None
        for job in jobs_list:
            if name == job.settings.name:
                job_id = job.job_id
                break

        try:
            # Convert dict to JobSettings object
            job_settings = JobSettings.from_dict(config_dict)
            response = workspace_client.jobs.reset(job_id=job_id, new_settings=job_settings)
            print(f"[SUCCESS] Reset Pipeline: {name}")
            return response
        except Exception as e:
            print(f"[ERROR] Reset Pipeline: {name} - {e}")
            raise

    except Exception as e:
        print(f"[ERROR] Create Pipeline: {name} - {e}")
        raise


def format_and_autofill_config(config, name, debug=False, **kwargs):

    # Read as String for Find & Replace
    config = open(config).read()

    # Autofill Kwargs
    for k, v in kwargs.items():
        config = config.replace("{{ " + k + " }}", v)

    # Convert to Dict
    config = ast.literal_eval(config)
    config["name"] = name

    # Autofill Metadata with Task Key
    silver = []
    for task in config["tasks"]:
        task_name = "_".join(task["task_key"].split("_")[1:])

        try:
            task["notebook_task"]["base_parameters"]["METADATA"] = task["notebook_task"][
                "base_parameters"
            ]["METADATA"].replace("{{ METADATA }}", task_name)
        except:
            pass

        # Auto dependency on Bronze
        if "silver" in task["task_key"] and "ref" not in task["task_key"]:
            silver.append({"task_key": task["task_key"]})
            task["depends_on"] = task.get("depends_on", []) + [{"task_key": f"bronze_{task_name}"}]

        # Auto dependency on Silver
        if "gold" in task["task_key"]:
            task["depends_on"] = task.get("depends_on", []) + silver

    # Overwrite Workflow Variables
    config = validate_and_update_config(config, name, debug, **kwargs)

    return config


def validate_and_update_config(config, name, debug=False, **kwargs):
    # Initialize clients within the function
    workspace_client = WorkspaceClient()

    # Retrive Organization ID
    try:
        org_id = spark.conf.get("spark.databricks.clusterUsageTags.clusterOwnerOrgId")
    except:
        org_id = "0"
    is_prd = org_id.endswith("5212")

    # PRD Config
    if is_prd:
        # Validate Branch
        branch = config["git_source"]["git_branch"]
        if branch not in ["stg", "main"]:
            raise ValueError("Valid ENV Parameters: [stg | main]")

        # Validate ENV
        for task in config["tasks"]:
            try:
                env = task["notebook_task"].get("base_parameters", {}).get("ENV")
                if env and env not in ["stg", "prd"]:
                    raise ValueError("Valid ENV Parameters: [stg | prd]")
            except:
                print("Current task is not a notebook task")
                continue

        # Get service principal name from kwargs
        service_principal_name = kwargs.get("service_principal_name", "prd_admin_principal")

        principal = create_or_get_service_principal(service_principal_name)
        config["run_as"] = {"service_principal_name": principal.application_id}

    if not debug:
        for task in config["tasks"]:
            # Update Job Compute
            try:
                del task["existing_cluster_id"]
                task["job_cluster_key"] = name
            except:
                print("Current task does not have existing_cluster_id")

        # Update Job Compute
        config["job_clusters"] = [
            {
                "job_cluster_key": name,
                "new_cluster": {
                    "aws_attributes": {
                        "first_on_demand": 1,
                        "availability": "SPOT_WITH_FALLBACK",
                        "instance_profile_arn": "arn:aws:iam::517783024470:instance-profile/iamr-databricks-glue",
                        "zone_id": "auto",
                    },
                    "data_security_mode": "SINGLE_USER",
                    "enable_elastic_disk": True,
                    "init_scripts": [
                        {
                            "volumes": {
                                "destination": "/Volumes/common/default/cluster/custom-cert.sh"
                            }
                        }
                    ],
                    "node_type_id": "c6gd.xlarge",
                    "num_workers": 3,
                    "spark_conf": {"spark.databricks.hive.metastore.glueCatalog.enabled": "true"},
                    "spark_version": "14.3.x-scala2.12",
                },
            }
        ]

    return config
