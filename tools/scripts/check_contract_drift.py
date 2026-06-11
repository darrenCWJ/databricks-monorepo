#!/usr/bin/env python3
"""Validate schema contracts against code and check input existence.

Two checks:
1. CONTRACT DRIFT — static analysis of src/*.py to detect columns written
   that aren't declared in contracts/schema.yml (and vice versa).
2. INPUT EXISTENCE — validates that every table declared in a project's
   AGENTS.md ## Inputs exists as an output in another project's
   contracts/schema.yml.

Usage:
    uv run python tools/scripts/check_contract_drift.py                           # All projects
    uv run python tools/scripts/check_contract_drift.py projects/finance/pipeline-foo  # One project
    uv run python tools/scripts/check_contract_drift.py --check-inputs            # Input existence only
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "scripts"))
from build_dep_graph import discover_projects, parse_agents_md_deps, parse_table_ref  # noqa: E402


def extract_columns_from_python(src_dir: Path) -> set[str]:
    """Static analysis: extract column names from PySpark code in src/."""
    columns: set[str] = set()

    if not src_dir.exists():
        return columns

    for py_file in src_dir.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for match in re.finditer(r"\.select\((.*?)\)", text, re.DOTALL):
            args = match.group(1)
            for col in re.findall(r'"([a-zA-Z_][a-zA-Z0-9_]*)"', args):
                columns.add(col)

        for match in re.finditer(r'\.withColumn\(\s*"([a-zA-Z_][a-zA-Z0-9_]*)"', text):
            columns.add(match.group(1))

        for match in re.finditer(
            r'\.withColumnRenamed\(\s*"[^"]*"\s*,\s*"([a-zA-Z_][a-zA-Z0-9_]*)"', text
        ):
            columns.add(match.group(1))

        for match in re.finditer(r'\.alias\(\s*"([a-zA-Z_][a-zA-Z0-9_]*)"', text):
            columns.add(match.group(1))

        for match in re.finditer(r'(?:F\.)?col\(\s*"([a-zA-Z_][a-zA-Z0-9_]*)"', text):
            columns.add(match.group(1))

        for match in re.finditer(r'StructField\(\s*"([a-zA-Z_][a-zA-Z0-9_]*)"', text):
            columns.add(match.group(1))

        for match in re.finditer(r'\["([a-zA-Z_][a-zA-Z0-9_]*)"\]', text):
            columns.add(match.group(1))

    return columns


def load_contract_columns(contract_path: Path) -> dict[str, set[str]]:
    """Load contracts/schema.yml and return {model_name: set of column names}."""
    if not contract_path.exists():
        return {}
    try:
        doc = yaml.safe_load(contract_path.read_text())
    except Exception:
        return {}
    if not isinstance(doc, dict):
        return {}

    result: dict[str, set[str]] = {}
    for model in doc.get("models", []) or []:
        model_name = model.get("name", "")
        cols: set[str] = set()
        for col in model.get("columns", []) or []:
            name = col.get("name", "")
            if name:
                cols.add(name)
        if model_name:
            result[model_name] = cols
    return result


def check_drift_for_project(project_path: Path) -> list[str]:
    """Check contract drift for a single project."""
    warnings: list[str] = []
    contract_path = project_path / "contracts" / "schema.yml"

    if not contract_path.exists():
        agents_md = project_path / "AGENTS.md"
        if agents_md.exists():
            deps = parse_agents_md_deps(agents_md)
            if deps["outputs"] and any(not e.startswith("(") for e in deps["outputs"]):
                warnings.append(
                    f"{project_path.relative_to(REPO_ROOT)}: "
                    f"has declared Outputs in AGENTS.md but no contracts/schema.yml"
                )
        return warnings

    contract_columns = load_contract_columns(contract_path)
    all_contract_cols: set[str] = set()
    for cols in contract_columns.values():
        all_contract_cols |= cols

    src_dirs = list(project_path.glob("src/*/"))
    if not src_dirs:
        return warnings

    code_columns = extract_columns_from_python(src_dirs[0].parent)

    contract_only = all_contract_cols - code_columns
    if contract_only:
        warnings.append(
            f"{project_path.relative_to(REPO_ROOT)}: "
            f"columns in contract but not found in code: {sorted(contract_only)}"
        )

    return warnings


def build_all_output_tables() -> dict[str, str]:
    """Build map of output table names from all contracts/schema.yml files."""
    output_tables: dict[str, str] = {}
    projects_root = REPO_ROOT / "projects"
    if not projects_root.exists():
        return output_tables

    for contract in projects_root.glob("*/*/contracts/schema.yml"):
        try:
            doc = yaml.safe_load(contract.read_text())
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        proj_rel = str(contract.parent.parent.relative_to(REPO_ROOT))
        for model in doc.get("models", []) or []:
            name = model.get("name", "")
            if name:
                output_tables[name] = proj_rel
                parts = name.split(".")
                if len(parts) > 1:
                    output_tables[parts[-1]] = proj_rel
    return output_tables


def check_input_existence() -> list[str]:
    """Validate that declared inputs exist as outputs in some contract."""
    warnings: list[str] = []
    output_tables = build_all_output_tables()

    projects = discover_projects()

    for proj_path, agents_md in projects.items():
        deps = parse_agents_md_deps(agents_md)
        for input_entry in deps["inputs"]:
            table = parse_table_ref(input_entry)
            if not table:
                continue
            normalized = re.sub(r"\$\{[^}]+\}\.", "", table)
            table_name = normalized.split(".")[-1] if "." in normalized else normalized

            found = False
            for registered_table in output_tables:
                if table_name in registered_table or registered_table in normalized:
                    found = True
                    break

            if not found and output_tables:
                warnings.append(
                    f"{proj_path}: input `{table}` not found in any project's "
                    f"contracts/schema.yml — may be external or uncontracted"
                )

    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", help="Project path to check (default: all)")
    parser.add_argument(
        "--check-inputs", action="store_true", help="Only run input existence check"
    )
    parser.add_argument(
        "--ci", action="store_true", help="Exit 1 on errors (missing contract with outputs)"
    )
    args = parser.parse_args()

    all_warnings: list[str] = []
    errors: list[str] = []

    if args.check_inputs:
        all_warnings.extend(check_input_existence())
    elif args.project:
        project_path = REPO_ROOT / args.project
        if not project_path.exists():
            print(f"Error: {args.project} does not exist", file=sys.stderr)
            return 1
        all_warnings.extend(check_drift_for_project(project_path))
    else:
        projects_root = REPO_ROOT / "projects"
        if projects_root.exists():
            for domain in sorted(projects_root.iterdir()):
                if not domain.is_dir() or domain.name.startswith("."):
                    continue
                for project in sorted(domain.iterdir()):
                    if project.is_dir():
                        all_warnings.extend(check_drift_for_project(project))

        all_warnings.extend(check_input_existence())

    if not all_warnings:
        print("OK: No contract drift detected. All declared inputs have matching outputs.")
        return 0

    for w in all_warnings:
        if "no contracts/schema.yml" in w:
            errors.append(w)
        else:
            print(f"  WARN: {w}")

    if errors:
        print("\nERRORS (must fix):")
        for e in errors:
            print(f"  - {e}")

    if args.ci and errors:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
