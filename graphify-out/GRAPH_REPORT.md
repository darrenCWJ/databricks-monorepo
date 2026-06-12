# Graph Report - .  (2026-06-12)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 975 nodes · 1482 edges · 83 communities (78 shown, 5 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 143 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3666d186`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]

## God Nodes (most connected - your core abstractions)
1. `print_success_or_error()` - 28 edges
2. `get_catalog()` - 22 edges
3. `TestUsersGroup` - 20 edges
4. `create_databricks_session()` - 18 edges
5. `get_repo_path()` - 17 edges
6. `SharePointOnline` - 17 edges
7. `create_initial()` - 16 edges
8. `SharePointConnector` - 15 edges
9. `set_securable_object_tag()` - 15 edges
10. `change_securable_object_owner()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `get_shared_cluster_policy()` --calls--> `print_success_or_error()`  [INFERRED]
  libs/de_databricks/src/de_databricks/compute/shared_compute.py → libs/de_databricks/src/de_databricks/common/utils.py
- `main()` --calls--> `create_databricks_session()`  [INFERRED]
  libs/de_databricks/notebooks/migrate/notebook/Step_1_Create_SP.py → libs/de_databricks/src/de_databricks/common/session.py
- `service_principal()` --calls--> `create_databricks_session()`  [INFERRED]
  libs/de_databricks/src/de_databricks/account/iam.py → libs/de_databricks/src/de_databricks/common/session.py
- `create_secret()` --calls--> `print_success_or_error()`  [INFERRED]
  libs/de_databricks/src/de_databricks/common/session.py → libs/de_databricks/src/de_databricks/common/utils.py
- `validate_catalog_replication()` --calls--> `create_databricks_session()`  [INFERRED]
  libs/de_databricks/src/de_databricks/migrate/db_validate_migrate.py → libs/de_databricks/src/de_databricks/common/session.py

## Import Cycles
- None detected.

## Communities (83 total, 5 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (65): categorise(), changed_files(), compute_downstream(), find_affected_scripts(), find_affected_skills(), main(), Compute downstream blast radius beyond direct changes., Find scripts in tools/scripts/ that import any of the changed libs. (+57 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (44): change_securable_object_owner(), grant_permission(), grant_securable_object_permission_in_dev(), Unity Catalog permission, ownership, and tagging operations.  All functions requ, Grant permissions on a table — only in DEV environment.      In staging/producti, Grant catalog-level privileges to project owners group.      Args:         spark, # TODO: need to remove this function once FIN domain removed it from their silve, # TODO: Add sub-domain owners / users / viewers (+36 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (31): get_catalog(), get_repo_path(), get_tables(), Catalog and path resolution utilities.  get_catalog and get_repo_path are pure f, Resolve Unity Catalog name from project + environment.      Args:         projec, Resolve the metadata folder path within a Databricks Workspace Repo.      Args:, Get all tables within a catalog's bronze schema.      Iterates through accessibl, create_gold() (+23 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (8): Tests for de_toolbox._legacy.copper_excel_csv — ported from test_copper.py., TestCheckColumns, TestCheckFileNameConvention, TestCheckFileType, TestCleanAndTitleColumnNames, TestConcatDictDataframes, TestConvertPath, TestMsToFormattedDate

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (28): Send email using Amazon SES SMTP      Parameters:     sender_email (str): Email, send_email(), get_wd_token(), Authentication utilities for external APIs.  Pure Python — no spark or dbutils d, Generate a Workday access token using JWT assertion.      Args:         client_i, Exception, Path, create_latest_temporal_view() (+20 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (14): format_object_principal(), is_valid_email(), is_valid_env(), is_valid_template(), Input validation utilities.  Pure functions — no spark or dbutils dependency., Validate email address format.      Checks RFC 5322 compliant pattern with addit, Check if environment string is valid for permission operations., Validate that a principal template uses only ${project} and ${env} placeholders. (+6 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (39): apply_byot(), check_columns(), check_file_name_convention(), check_file_type(), clean_and_title_column_names(), clear_all_files(), concat_dict_dataframes(), convert_path() (+31 more)

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (19): create_or_get_service_principal(), Create or get a service principal using Databricks SDK      Args:         displa, create_databricks_acct_sdk(), create_databricks_acct_session(), create_databricks_session(), create_databricks_workspace_session(), create_secret(), create_tableau_session() (+11 more)

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (30): create_and_replicate_catalog(), get_table_comment(), get_view_comment(), migrate_catalog_permissions(), migrate_schema_permissions(), migrate_table_permissions(), migrate_view_permissions(), migrate_volume_permissions() (+22 more)

### Community 9 - "Community 9"
Cohesion: 0.09
Nodes (16): delete_asset(), delete_schema(), get_catalog_and_schema_info(), get_table_or_volume_info(), housekeep_catalog(), is_deletion_date(), email_admin_report(), notify_inactive_users() (+8 more)

### Community 10 - "Community 10"
Cohesion: 0.09
Nodes (31): apply_byot(), check_columns(), check_file_name_convention(), check_file_type(), clean_and_title_column_names(), clear_all_files(), concat_dict_dataframes(), convert_path() (+23 more)

### Community 11 - "Community 11"
Cohesion: 0.11
Nodes (8): run_sharepoint(), SharePointConnector, Tests for de_toolbox.connectors.sharepoint — ported from test_sharepoint.py., TestCleanPath, TestCreateSharepointSession, TestGetAllLists, TestGetFirstPathElement, TestSavePandasDfToVolume

### Community 12 - "Community 12"
Cohesion: 0.14
Nodes (27): build_report(), cell(), compute_actions(), _div(), folder_in_codeowners(), FolderStatus, HealthReport, main() (+19 more)

### Community 13 - "Community 13"
Cohesion: 0.08
Nodes (11): Integration tests requiring a live Databricks/Spark connection.  Ported from: te, Requires: databricks_dq_<env>.<project> tables + GE., Requires: test_dev.bronze.unit_test table., Requires: test_dev.silver hub/sat tables., Requires: test_dev.gold dim/fact tables., Requires: databricks_dq_<env>.<project> tables., TestAutoloader, TestDataQuality (+3 more)

### Community 14 - "Community 14"
Cohesion: 0.16
Nodes (8): call_wd_api(), get_wd_dates(), get_wd_wid(), Tests for de_toolbox.connectors.workday — call_wd_api, get_wd_dates, get_wd_wid., Create a mock Row returned by spark.sql().collect()[0].asDict()., TestCallWdApi, TestGetWdDates, TestGetWdWid

### Community 15 - "Community 15"
Cohesion: 0.25
Nodes (3): get_key(), main_SharePointOnline(), SharePointOnline

### Community 16 - "Community 16"
Cohesion: 0.15
Nodes (12): check_identity_type(), convert_session_account(), create_update_permissions_assignment(), get_service_principal_details(), list_group_details(), Function to get group details, that equal the given group name.      Args:, Check if the given string is a user email, service principal name/id, or group n, Function to assign group into workspace depended upon the environment that the c (+4 more)

### Community 17 - "Community 17"
Cohesion: 0.26
Nodes (15): _common_agents_md(), main(), # TODO: implement pipeline logic, # TODO: implement streaming logic, # TODO: implement capture logic, scaffold_api(), scaffold_app(), scaffold_capture() (+7 more)

### Community 18 - "Community 18"
Cohesion: 0.23
Nodes (7): create_or_get_service_principal(), create_or_update_service_principal_git_token(), create_or_update_service_principal_token(), housekeep_service_principal(), service_principal(), print_success_or_error(), TestAccountIam

### Community 19 - "Community 19"
Cohesion: 0.29
Nodes (13): CompletedProcess, export_raw_job(), generate_bundle(), main(), pull_notebooks(), Find every workspace notebook the job references and copy it into ./notebooks/., Dump the raw job JSON for the IMPORT_REPORT reference., Use `databricks bundle generate job` to produce starter YAML. (+5 more)

### Community 20 - "Community 20"
Cohesion: 0.21
Nodes (5): delete_group(), Function to delete a group.      Args:         session (common.session.CustomSes, Function to add users into a group.      Args:         session (common.session.C, update_group_details_members(), TestUsersGroup

### Community 21 - "Community 21"
Cohesion: 0.19
Nodes (5): TestWorkflowJob, create_or_update_job(), create_trigger_once_job(), format_and_autofill_config(), validate_and_update_config()

### Community 22 - "Community 22"
Cohesion: 0.17
Nodes (9): CustomResponse, is_valid_email(), Function to validate email address.      Args:         email (str): email addres, Function to validate and convert group name to the correct naming convention., validate_group_name(), create_new_user(), Function to create user using email, would also set user name as their email. Th, Test pure-Python utilities that don't require Databricks runtime.      The utils (+1 more)

### Community 23 - "Community 23"
Cohesion: 0.18
Nodes (11): create_monthly_snapshot(), get_month_end_dates(), Monthly snapshot creation for gold-layer reporting.  Creates point-in-time snaps, Generate list of month-end dates between start_date and end_date (inclusive)., Create snapshot data by period (month-end) or current (latest only).      Adds r, SparkSession, DataFrame, SparkSession (+3 more)

### Community 24 - "Community 24"
Cohesion: 0.22
Nodes (12): Validate that all objects and permissions were successfully replicated between c, Validate catalog-level permissions match, Validate schema-level permissions match, Validate table-level permissions match, Validate view-level permissions match, Validate volume-level permissions match, validate_catalog_permissions(), validate_catalog_replication() (+4 more)

### Community 25 - "Community 25"
Cohesion: 0.20
Nodes (6): create_shared_cluster(), get_shared_cluster_policy(), Set parameters as default configuration to create the cluster, Only allow respective group to access the shared cluster     E.g. uat_hcm_owners, set_cluster_permissions(), TestCreateCompute

### Community 26 - "Community 26"
Cohesion: 0.25
Nodes (10): create_external_location(), create_storage_credential(), get_catalog_admin_service_principals(), grant_create_managed_storage_permission(), Create an external location using storage credential, Grant CREATE MANAGED STORAGE permission to service principal, Setup single storage credential, external location, and permissions for migratio, Get all catalog admin service principals for the specified environment (+2 more)

### Community 27 - "Community 27"
Cohesion: 0.29
Nodes (10): discover_lib_packages(), find_lib_imports_in_file(), get_project_declared_deps(), main(), project_of(), Find all importable package names under libs/., Extract dependency names from a project's pyproject.toml., Find which lib packages are imported in a Python file. (+2 more)

### Community 28 - "Community 28"
Cohesion: 0.20
Nodes (6): create_new_group(), get_user_details(), Function to get user details for the given user name.      Args:         session, Function to create a group with users already being assigned to it.      Args:, Function to update the permissions of a securable_type and securable_name of the, update_permissions()

### Community 29 - "Community 29"
Cohesion: 0.31
Nodes (9): extract_source_app(), generate_data_architecture(), main(), parse_agents_md(), Generate docs/data-architecture.md from per-app AGENTS.md declarations.  Reads #, Extract structured sections from an AGENTS.md file., Extract the source app/project name from an input entry like 'cdo.silver.fct_ord, Generate the full data-architecture.md content. (+1 more)

### Community 30 - "Community 30"
Cohesion: 0.38
Nodes (9): _div(), LibInfo, main(), parse_lib_agents_md(), print_report(), Discover available shared libraries and what they provide.  Scans libs/*/AGENTS., _row(), scan_libs() (+1 more)

### Community 31 - "Community 31"
Cohesion: 0.28
Nodes (8): SparkSession, _add_hash_key(), create_bronze_table(), _process_dataframe(), Bronze layer — flatten nested structs, add hash key, save with column mapping., Add SHA-256 hash of all non-metadata columns., Flatten copper data and write to bronze Delta table.      Args:         spark: A, Recursively flatten structs and explode complex arrays.

### Community 32 - "Community 32"
Cohesion: 0.25
Nodes (8): SparkSession, _compute_stats(), profile_data(), Data profiling — compute column-level statistics for any DataFrame.  Supports ne, Compute statistics for a single field., Compute statistics for each column in a DataFrame.      Args:         df: Input, Convert profiling stats to DataFrame and optionally save.      Args:         spa, write_to_table()

### Community 33 - "Community 33"
Cohesion: 0.50
Nodes (8): check_folder_coverage(), check_graph_nodes(), check_runtime_deps(), find_agents_md_files(), load_graph(), main(), parse_section_items(), Path

### Community 34 - "Community 34"
Cohesion: 0.25
Nodes (5): Delta table write operations with column mapping support.  Handles append, overw, de_toolbox — Shared Databricks pipeline library.  Public API re-exports. Import, Email notification utilities.  Uses Amazon SES SMTP. Requires a get_secret calla, Send HTML email via Amazon SES SMTP.      Args:         sender_email: Sender ema, send_email()

### Community 35 - "Community 35"
Cohesion: 0.25
Nodes (7): Save DataFrame to Delta table with column mapping enabled (id mode).      Handle, save_df_to_delta_with_column_mapping(), Internal implementation of save_df_to_delta_with_column_mapping.  Do not import, Clean DataFrame columns for Parquet compatibility and optionally save to Delta t, _save_df_to_delta_with_column_mapping(), DataFrame, SparkSession

### Community 36 - "Community 36"
Cohesion: 0.43
Nodes (7): codeowners_groups(), codeowners_lines(), main(), Parse CODEOWNERS into [(path_glob, [groups])]., referenced_groups(), scan_file(), Path

### Community 37 - "Community 37"
Cohesion: 0.36
Nodes (7): find_app_consumers(), find_in_files(), find_in_manifest(), main(), Signal 2: filesystem scan under dbt/*/models/., Signal 1: dbt manifest, if any project has parsed., Signal 5: grep data-architecture.md for app-side references.      Returns app na

### Community 38 - "Community 38"
Cohesion: 0.62
Nodes (5): import_sp(), import_storage_module(), import_user(), tf_import(), import.sh script

### Community 39 - "Community 39"
Cohesion: 0.33
Nodes (6): compute_stats(), profile_data(), Compute statistics for field.         Statistics calculated:             dtype:, Convert dictionary into a DLT.      Params:         data_dict: data source in di, Iterate through the dataset and calculate statistics for each field and subfield, write_to_table()

### Community 40 - "Community 40"
Cohesion: 0.33
Nodes (6): DataFrame, clean_columns_aggressive(), clean_columns_for_column_mapping(), Column cleaning utilities for pipeline layers.  Provides naming convention trans, Minimal cleaning for Delta column mapping compatibility.      Replaces only char, Column cleaning with naming convention enforcement.      Used in silver layer to

### Community 41 - "Community 41"
Cohesion: 0.33
Nodes (6): SparkSession, _apply_transforms(), create_silver_table(), Silver layer — transform, rename, clean naming conventions, save.  Reads from br, Apply BYOT (Bring Your Own Transform) operations from config., Transform bronze data and write to silver Delta table.      Args:         spark:

### Community 42 - "Community 42"
Cohesion: 0.48
Nodes (6): app_of(), check_file(), main(), Return the project name if path is under projects/<domain>/<name>/, else None., Return a list of error messages for cross-app imports in this file., Path

### Community 43 - "Community 43"
Cohesion: 0.29
Nodes (6): get_effective_permissions(), get_permissions(), Function to get the permissions of a securable_type and securable_name.      Arg, Function to gets the effective permissions for a securable. Effective permission, Function to update the permissions of a securable_type and securable_name of the, update_permissions()

### Community 44 - "Community 44"
Cohesion: 0.33
Nodes (5): Minimal local pytest that verifies the package structure imports correctly.  Not, Verify the de_databricks package is discoverable., Verify all expected subpackages exist as importable modules., test_package_exists(), test_subpackage_structure()

### Community 45 - "Community 45"
Cohesion: 0.40
Nodes (4): SparkSession, create_copper_table(), Copper layer — Auto Loader ingestion from raw files (JSON/CSV).  Reads from Data, Ingest raw files into a copper-layer Delta table via Auto Loader.      Args:

### Community 46 - "Community 46"
Cohesion: 0.50
Nodes (4): main(), parse_codeowners(), Return list of (path_glob, owner) tuples from CODEOWNERS., # TODO: hook up to Databricks SDK for workspace ACLs + UC grants

### Community 47 - "Community 47"
Cohesion: 0.83
Nodes (3): wd_period_lookup(), wd_year_lookup(), workday_api()

### Community 49 - "Community 49"
Cohesion: 0.50
Nodes (3): DataFrame, process_bronze_to_mart_snapshot(), Reads a bronze table, filters by maximum _LOAD_DTS, and optionally saves to mart

### Community 50 - "Community 50"
Cohesion: 0.83
Nodes (3): check_file(), main(), Path

### Community 51 - "Community 51"
Cohesion: 0.83
Nodes (3): lint(), main(), Path

## Knowledge Gaps
- **16 isolated node(s):** `scan-environment.sh script`, `SparkSession`, `SparkSession`, `DataFrame`, `SparkSession` (+11 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `print_success_or_error()` connect `Community 18` to `Community 7`, `Community 8`, `Community 43`, `Community 16`, `Community 20`, `Community 22`, `Community 25`, `Community 28`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Why does `create_databricks_session()` connect `Community 7` to `Community 2`, `Community 8`, `Community 16`, `Community 18`, `Community 21`, `Community 24`, `Community 25`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `get_catalog()` connect `Community 2` to `Community 1`, `Community 6`, `Community 7`, `Community 10`, `Community 11`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `print_success_or_error()` (e.g. with `create_or_get_service_principal()` and `create_or_update_service_principal_git_token()`) actually correct?**
  _`print_success_or_error()` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `get_catalog()` (e.g. with `create_catalog_and_schemas()` and `main()`) actually correct?**
  _`get_catalog()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `create_databricks_session()` (e.g. with `service_principal()` and `validate_catalog_replication()`) actually correct?**
  _`create_databricks_session()` has 13 INFERRED edges - model-reasoned connections that need verification._
- **What connects `scan-environment.sh script`, `Assign MANAGE permission to service principal for a specific catalog using SQL`, `Assign ALL PRIVILEGES permissions to catalog admin using SQL` to the rest of the system?**
  _223 weakly-connected nodes found - possible documentation gaps or missing edges._