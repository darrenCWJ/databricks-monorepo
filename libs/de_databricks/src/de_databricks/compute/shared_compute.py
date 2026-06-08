from de_databricks.common.utils import *


def get_shared_cluster_policy(session):
    response = session.get("policies/clusters/list").json()

    # Get shared cluster policy id
    response_lst = response["policies"]
    for k in response_lst:
        if k["name"] == "Shared Compute":
            print_success_or_error(response, "List Shared Cluster Policy Id")
            return k["policy_id"]


def create_shared_cluster(session, PROJECT):
    """
    Set parameters as default configuration to create the cluster
    """

    default_config = {
        "cluster_name": f"{PROJECT.upper()}'s Cluster",
        "spark_version": "13.1.x-scala2.12",
        "node_type_id": "m4.xlarge",
        "autoscale": {"min_workers": 1, "max_workers": 3},
        "spark_conf": {"spark.databricks.sql.initial.catalog.name": "main"},
        "enable_local_disk_encryption": False,
        "enable_elastic_disk": True,
        "data_security_mode": "USER_ISOLATION",
        "autotermination_minutes": 60,
    }

    response = session.post("clusters/create", json=default_config)
    print_success_or_error(response, "Created shared cluster")
    return response


def set_cluster_permissions(session, PROJECT, ENV):
    """
    Only allow respective group to access the shared cluster
    E.g. uat_hcm_owners will only be able to access "HCM's Cluster"
    """

    # Get cluster id
    cluster_id = ""
    cluster_name = ""
    response_cluster = session.get("clusters/list").json()
    response_cluster_lst = response_cluster["clusters"]
    for k in response_cluster_lst:
        if k["cluster_name"] == f"{PROJECT.upper()}'s Cluster":
            cluster_id += k["cluster_id"]
            cluster_name += k["cluster_name"]

    # Get respective user group
    group_name = []
    response_group = session.get("preview/scim/v2/Groups").json()
    response_group_lst = response_group["Resources"]

    for k in response_group_lst:
        if k["displayName"].startswith(f"{ENV}_{PROJECT.lower()}"):
            group_name.append(k["displayName"])

    acl_lst = []
    for group in group_name:
        acl_group = {"group_name": f"{group}", "permission_level": "CAN_RESTART"}
        acl_lst.append(acl_group)

    default_config = {"access_control_list": acl_lst}

    response = session.put(f"permissions/clusters/{cluster_id}", json=default_config)
    print_success_or_error(response, f"Granted {group_name} to manage '{cluster_name}' cluster")
    return response
