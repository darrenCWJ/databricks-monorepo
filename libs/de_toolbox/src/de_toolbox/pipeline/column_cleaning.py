"""Column cleaning utilities for pipeline layers.

Provides naming convention transforms and column-mapping-safe cleaning.
"""

import re

from pyspark.sql import DataFrame

METADATA_COLUMNS = frozenset(
    {
        "_rescued_data",
        "_LOAD_DTS",
        "_LOAD_DATE",
        "_SOURCE_FILE_BYTES",
        "_SOURCE_FILE_MODIFIED",
        "_SOURCE_FILE_NAME",
        "_INGEST_DATE",
        "_INGEST_DTS",
    }
)


def clean_columns_for_column_mapping(df: DataFrame) -> tuple[DataFrame, dict]:
    """Minimal cleaning for Delta column mapping compatibility.

    Replaces only characters disallowed by column mapping id mode:
    periods, forward slashes, ASCII control chars, DELETE char.
    Metadata columns are preserved without modification.

    Args:
        df: Input DataFrame.

    Returns:
        Tuple of (cleaned DataFrame, mapping of cleaned->original names).
    """
    original_columns = df.columns
    column_mapping = {}
    cleaned_columns = []

    for original_col in original_columns:
        if original_col in METADATA_COLUMNS:
            cleaned_columns.append(original_col)
            continue

        cleaned_col = re.sub(r"[./\x00-\x1F\x7F]", " ", original_col)
        cleaned_col = re.sub(r"\s+", " ", cleaned_col).strip()

        if not cleaned_col:
            cleaned_col = "unnamed_column"

        base_cleaned = cleaned_col
        counter = 1
        while cleaned_col in cleaned_columns:
            cleaned_col = f"{base_cleaned}_{counter}"
            counter += 1

        cleaned_columns.append(cleaned_col)
        if cleaned_col != original_col:
            column_mapping[cleaned_col] = original_col

    df_renamed = df.toDF(*cleaned_columns)
    return df_renamed, column_mapping


def clean_columns_aggressive(
    df: DataFrame, column_naming_convention: str = "pascal"
) -> tuple[DataFrame, dict]:
    """Column cleaning with naming convention enforcement.

    Used in silver layer to standardize column names.

    Args:
        df: Input DataFrame.
        column_naming_convention: One of "pascal", "camel", "snake", "sanitized".

    Returns:
        Tuple of (cleaned DataFrame, mapping of cleaned->original names).
    """
    original_columns = df.columns
    column_mapping = {}
    cleaned_columns = []

    for col_name in original_columns:
        if col_name in METADATA_COLUMNS:
            cleaned_columns.append(col_name)
            continue

        if column_naming_convention.lower() == "sanitized":
            cleaned_col = re.sub(r"[^A-Za-z0-9_]+", "_", col_name)
        else:
            temp_col = re.sub(r"[^A-Za-z0-9]+", " ", col_name)
            temp_col = re.sub(r"\s+", " ", temp_col).strip()
            words = [w for w in temp_col.split() if w]

            if words:
                if column_naming_convention.lower() == "pascal":
                    cleaned_col = "".join(w.capitalize() for w in words)
                elif column_naming_convention.lower() == "camel":
                    cleaned_col = words[0].lower() + "".join(w.capitalize() for w in words[1:])
                elif column_naming_convention.lower() == "snake":
                    cleaned_col = "_".join(w.lower() for w in words)
                else:
                    cleaned_col = "".join(w.capitalize() for w in words)
            else:
                fallback = {
                    "pascal": "UnnamedColumn",
                    "camel": "unnamedColumn",
                    "snake": "unnamed_column",
                    "sanitized": "unnamed_column",
                }
                cleaned_col = fallback.get(column_naming_convention.lower(), "UnnamedColumn")

        base_cleaned = cleaned_col
        counter = 1
        while cleaned_col in cleaned_columns:
            cleaned_col = f"{base_cleaned}_{counter}"
            counter += 1

        cleaned_columns.append(cleaned_col)
        if cleaned_col != col_name:
            column_mapping[cleaned_col] = col_name

    df_renamed = df.toDF(*cleaned_columns)
    return df_renamed, column_mapping
