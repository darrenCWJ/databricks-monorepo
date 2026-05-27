#!/usr/bin/env python3
"""Compute the set of DABs and libs affected by the current git diff.

Used by CI to fan out per-scope jobs.

Usage:
    uv run python tools/scripts/affected.py [BASE_REF]

Output: JSON to stdout with:
    {
        "apps": ["customer360-etl", ...],
        "libs": ["common-spark", ...],
        "dbt":  ["platform-core", ...],
        "global_changes": false  # true if root config touched -> run everything
    }
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GLOBAL_FILES = {
    "pyproject.toml",
    "uv.lock",
    "databricks.yml",
    "justfile",
    ".pre-commit-config.yaml",
}


def changed_files(base: str = "origin/main") -> list[str]:
    out = subprocess.check_output(["git", "diff", "--name-only", f"{base}...HEAD"], cwd=REPO_ROOT)
    return out.decode().splitlines()


def lib_consumers(lib_name: str) -> set[str]:
    """Find apps whose pyproject.toml declares dependency on this lib."""
    consumers: set[str] = set()
    for pyproj in (REPO_ROOT / "apps").glob("*/pyproject.toml"):
        text = pyproj.read_text()
        if lib_name in text:
            consumers.add(pyproj.parent.name)
    return consumers


def categorise(paths: Iterable[str]) -> dict:
    apps: set[str] = set()
    libs: set[str] = set()
    dbt_projects: set[str] = set()
    global_changes = False
    for p in paths:
        if not p:
            continue
        parts = p.split("/")
        if p in GLOBAL_FILES or parts[0] in {".github", "infra", "tools"}:
            global_changes = True
            continue
        if parts[0] == "apps" and len(parts) > 1:
            apps.add(parts[1])
        elif parts[0] == "libs" and len(parts) > 1:
            lib = parts[1]
            libs.add(lib)
            apps |= lib_consumers(lib)
        elif parts[0] == "dbt" and len(parts) > 1:
            dbt_projects.add(parts[1])
    return {
        "apps": sorted(apps),
        "libs": sorted(libs),
        "dbt": sorted(dbt_projects),
        "global_changes": global_changes,
    }


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    paths = changed_files(base)
    result = categorise(paths)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
