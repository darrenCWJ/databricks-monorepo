#!/usr/bin/env python3
"""Detect breaking schema changes in contracts/schema.yml and report downstream impact.

Breaking changes:
- Column removed (present in old, missing in new)
- Column type changed (data_type differs between old and new)

Non-breaking (safe):
- Column added
- Description or meta changed (without type change)

Usage:
    uv run python tools/scripts/check_schema_breaking.py              # Check staged changes
    uv run python tools/scripts/check_schema_breaking.py --base main  # Compare against branch
    uv run python tools/scripts/check_schema_breaking.py --ci         # Exit 1 if breaking + downstream exists
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "scripts"))
from build_dep_graph import build_table_consumer_map, discover_projects  # noqa: E402


def get_old_file_content(path: str, base: str) -> str | None:
    """Get the content of a file at the base ref via git show."""
    try:
        out = subprocess.check_output(
            ["git", "show", f"{base}:{path}"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
        )
        return out.decode("utf-8")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def parse_schema_columns(content: str) -> dict[str, dict]:
    """Parse contracts/schema.yml into {model.column_name: {data_type, ...}}."""
    columns: dict[str, dict] = {}
    try:
        doc = yaml.safe_load(content)
    except Exception:
        return columns
    if not isinstance(doc, dict):
        return columns
    for model in doc.get("models", []) or []:
        model_name = model.get("name", "")
        for col in model.get("columns", []) or []:
            col_name = col.get("name", "")
            key = f"{model_name}.{col_name}"
            columns[key] = {
                "data_type": col.get("data_type", ""),
                "model": model_name,
                "column": col_name,
            }
    return columns


def detect_breaking_changes(old_content: str, new_content: str) -> list[dict]:
    """Compare old vs new schema and return list of breaking changes."""
    old_cols = parse_schema_columns(old_content)
    new_cols = parse_schema_columns(new_content)

    breaks: list[dict] = []

    for key, old_info in old_cols.items():
        if key not in new_cols:
            breaks.append(
                {
                    "type": "column_removed",
                    "model": old_info["model"],
                    "column": old_info["column"],
                    "old_type": old_info["data_type"],
                }
            )
        elif old_info["data_type"] != new_cols[key]["data_type"]:
            breaks.append(
                {
                    "type": "type_changed",
                    "model": old_info["model"],
                    "column": old_info["column"],
                    "old_type": old_info["data_type"],
                    "new_type": new_cols[key]["data_type"],
                }
            )

    return breaks


def find_changed_schema_files(base: str) -> list[str]:
    """Find contracts/schema.yml files changed in the current diff."""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            cwd=REPO_ROOT,
        )
        files = out.decode().splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            out = subprocess.check_output(
                ["git", "diff", "--cached", "--name-only"],
                cwd=REPO_ROOT,
            )
            files = out.decode().splitlines()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []

    return [f for f in files if "contracts/schema.yml" in f]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main", help="Base ref to compare against")
    parser.add_argument(
        "--ci", action="store_true", help="Exit 1 if breaking changes affect downstream"
    )
    args = parser.parse_args()

    changed_schemas = find_changed_schema_files(args.base)

    if not changed_schemas:
        print("No contracts/schema.yml files changed.")
        return 0

    projects = discover_projects()
    table_consumers = build_table_consumer_map(projects)

    all_breaks: list[dict] = []
    all_downstream: set[str] = set()

    for schema_file in changed_schemas:
        old_content = get_old_file_content(schema_file, args.base)
        new_path = REPO_ROOT / schema_file
        if not new_path.exists():
            continue
        new_content = new_path.read_text()

        if old_content is None:
            continue

        breaks = detect_breaking_changes(old_content, new_content)
        if not breaks:
            continue

        try:
            doc = yaml.safe_load(new_content)
            affected_tables = [m.get("name", "") for m in (doc.get("models", []) or [])]
        except Exception:
            affected_tables = []

        downstream: set[str] = set()
        for table in affected_tables:
            for full_table, consumers in table_consumers.items():
                if table in full_table:
                    downstream |= consumers

        schema_path = Path(schema_file)
        proj_rel = str(schema_path.parent.parent.relative_to(Path(".")))
        downstream.discard(proj_rel)

        for b in breaks:
            b["schema_file"] = schema_file
            b["downstream_projects"] = sorted(downstream)

        all_breaks.extend(breaks)
        all_downstream |= downstream

    if not all_breaks:
        print("Schema changes detected but none are breaking.")
        return 0

    print("=" * 70)
    print("BREAKING SCHEMA CHANGES DETECTED")
    print("=" * 70)
    for b in all_breaks:
        if b["type"] == "column_removed":
            print(f"  REMOVED: {b['model']}.{b['column']} (was {b['old_type']})")
        elif b["type"] == "type_changed":
            print(f"  TYPE CHANGED: {b['model']}.{b['column']}: {b['old_type']} -> {b['new_type']}")
        print(f"    Source: {b['schema_file']}")

    if all_downstream:
        print()
        print("DOWNSTREAM PROJECTS AFFECTED:")
        for proj in sorted(all_downstream):
            print(f"  - {proj}")
        print()
        print("These projects consume tables with breaking changes.")
        print("Coordinate with owners or confirm the break is intentional.")
    else:
        print()
        print("No downstream consumers found for the affected tables.")

    print("=" * 70)

    if args.ci and all_downstream:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
