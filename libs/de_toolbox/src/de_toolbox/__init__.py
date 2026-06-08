"""de_toolbox — Shared Databricks pipeline library.

Public API re-exports. Import directly from here for convenience:
    from de_toolbox import create_copper_table, create_bronze_table
"""

from de_toolbox.catalog import get_catalog, get_repo_path
from de_toolbox.delta import save_df_to_delta_with_column_mapping
from de_toolbox.notifications import send_email
from de_toolbox.permissions import (
    change_securable_object_owner,
    format_object_principal,
    grant_securable_object_permission_in_dev,
    set_securable_object_tag,
)
from de_toolbox.pipeline.bronze import create_bronze_table
from de_toolbox.pipeline.copper import create_copper_table
from de_toolbox.pipeline.gold import create_gold_table
from de_toolbox.pipeline.silver import create_silver_table
from de_toolbox.snapshot import create_monthly_snapshot, get_month_end_dates
from de_toolbox.validation import is_valid_email, is_valid_env, is_valid_template

__all__ = [
    "get_catalog",
    "get_repo_path",
    "is_valid_email",
    "is_valid_env",
    "is_valid_template",
    "change_securable_object_owner",
    "format_object_principal",
    "grant_securable_object_permission_in_dev",
    "set_securable_object_tag",
    "save_df_to_delta_with_column_mapping",
    "create_monthly_snapshot",
    "get_month_end_dates",
    "send_email",
    "create_copper_table",
    "create_bronze_table",
    "create_silver_table",
    "create_gold_table",
]
