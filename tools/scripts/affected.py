#!/usr/bin/env python3
"""Compute the set of DABs and libs affected by the current git diff.

Used by CI to fan out per-scope jobs. Includes enhanced blast radius detection:
- Direct file changes (which project/lib was modified)
- Transitive lib dependencies (full closure)
- Schema-breaking changes (downstream table consumers)
- Runtime dependencies (projects that depend on changed projects)

Usage:
    uv run python tools/scripts/affected.py [BASE_REF]

Output: JSON to stdout with:
    {
        "projects": ["finance/pipeline-foo", ...],
        "libs": ["common-spark", ...],
        "dbt":  ["platform-core", ...],
        "global_changes": false,
        "downstream_affected": {
            "schema_breaking": ["hcm/pipeline-bar"],
            "runtime_deps": ["finance/app-viewer"],
            "lib_transitive": ["finance/pipeline-baz"]
        },
        "scripts_affected": ["tools/scripts/affected.py", ...],
        "skills_affected": [".claude/skills/autoloader-medallion", ...]
    }
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "scripts"))

from build_dep_graph import (  # noqa: E402
    all_transitive_lib_consumers,
    build_reverse_runtime_graph,
    build_runtime_dep_graph,
    build_table_consumer_map,
    discover_libs,
    discover_projects,
)

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


def categorise(paths: Iterable[str]) -> dict:
    """Categorise changed files into direct scopes."""
    apps: set[str] = set()
    libs_changed: set[str] = set()
    dbt_projects: set[str] = set()
    global_changes = False
    schema_files_changed: list[str] = []

    for p in paths:
        if not p:
            continue
        parts = p.split("/")
        if p in GLOBAL_FILES or parts[0] in {".github", "infra", "tools"}:
            global_changes = True
            continue
        if parts[0] == "projects" and len(parts) > 2:
            apps.add(f"{parts[1]}/{parts[2]}")
        elif parts[0] == "libs" and len(parts) > 1:
            libs_changed.add(parts[1])
        elif parts[0] == "dbt" and len(parts) > 1:
            dbt_projects.add(parts[1])

        if "contracts/schema.yml" in p:
            schema_files_changed.append(p)

    return {
        "projects": apps,
        "libs": libs_changed,
        "dbt": dbt_projects,
        "global_changes": global_changes,
        "_schema_files_changed": schema_files_changed,
    }


def compute_downstream(
    direct_projects: set[str],
    direct_libs: set[str],
    schema_files: list[str],
    base: str,
) -> dict[str, list[str]]:
    """Compute downstream blast radius beyond direct changes."""
    downstream: dict[str, set[str]] = {
        "schema_breaking": set(),
        "runtime_deps": set(),
        "lib_transitive": set(),
    }

    # 1. Transitive lib consumers
    if direct_libs:
        libs = discover_libs()
        lib_consumers = all_transitive_lib_consumers(direct_libs, libs)
        extra = lib_consumers - direct_projects
        downstream["lib_transitive"] = extra

    # 2. Schema-breaking downstream
    if schema_files:
        try:
            import yaml

            projects = discover_projects()
            table_consumers = build_table_consumer_map(projects)

            for schema_file in schema_files:
                try:
                    old_out = subprocess.check_output(
                        ["git", "show", f"{base}:{schema_file}"],
                        cwd=REPO_ROOT,
                        stderr=subprocess.DEVNULL,
                    )
                    old_content = old_out.decode()
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue

                new_path = REPO_ROOT / schema_file
                if not new_path.exists():
                    continue

                old_doc = yaml.safe_load(old_content) or {}
                new_doc = yaml.safe_load(new_path.read_text()) or {}

                old_cols: dict[str, str] = {}
                for m in old_doc.get("models", []) or []:
                    for c in m.get("columns", []) or []:
                        old_cols[f"{m['name']}.{c['name']}"] = c.get("data_type", "")

                new_cols: dict[str, str] = {}
                for m in new_doc.get("models", []) or []:
                    for c in m.get("columns", []) or []:
                        new_cols[f"{m['name']}.{c['name']}"] = c.get("data_type", "")

                has_breaking = False
                for key, old_type in old_cols.items():
                    if key not in new_cols or old_type != new_cols.get(key, ""):
                        has_breaking = True
                        break

                if has_breaking:
                    affected_tables = [m.get("name", "") for m in (new_doc.get("models", []) or [])]
                    for table in affected_tables:
                        for full_table, consumers in table_consumers.items():
                            if table in full_table:
                                downstream["schema_breaking"] |= consumers

        except ImportError:
            pass

    # 3. Runtime dependents
    if direct_projects:
        projects = discover_projects()
        runtime_graph = build_runtime_dep_graph(projects)
        reverse_runtime = build_reverse_runtime_graph(runtime_graph)

        for proj in direct_projects:
            full_path = f"projects/{proj}"
            dependents = reverse_runtime.get(full_path, set())
            for dep in dependents:
                rel = dep.replace("projects/", "", 1)
                if rel not in direct_projects:
                    downstream["runtime_deps"].add(rel)

    # Remove self-references
    for key in downstream:
        downstream[key] -= direct_projects

    return {k: sorted(v) for k, v in downstream.items()}


def find_affected_scripts(changed_libs: set[str]) -> list[str]:
    """Find scripts in tools/scripts/ that import any of the changed libs."""
    if not changed_libs:
        return []

    scripts_dir = REPO_ROOT / "tools" / "scripts"
    if not scripts_dir.exists():
        return []

    affected: set[str] = set()
    lib_packages = {lib_name.replace("-", "_") for lib_name in changed_libs}

    for script in scripts_dir.glob("*.py"):
        try:
            content = script.read_text()
        except OSError:
            continue
        for pkg in lib_packages:
            if f"from {pkg}" in content or f"import {pkg}" in content:
                affected.add(f"tools/scripts/{script.name}")
                break

    return sorted(affected)


def find_affected_skills(changed_libs: set[str]) -> list[str]:
    """Find skills that declare a dependency on any of the changed libs."""
    if not changed_libs:
        return []

    skills_dir = REPO_ROOT / ".claude" / "skills"
    if not skills_dir.exists():
        return []

    affected: set[str] = set()
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            content = skill_md.read_text()
        except OSError:
            continue
        for lib_name in changed_libs:
            if f"libs/{lib_name}" in content or lib_name.replace("-", "_") in content:
                affected.add(f".claude/skills/{skill_dir.name}")
                break

    return sorted(affected)


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    paths = changed_files(base)
    result = categorise(paths)

    direct_projects = result.pop("projects")
    direct_libs = result.pop("libs")
    schema_files = result.pop("_schema_files_changed")

    # Also add direct lib consumers (non-transitive, for backwards compat)
    _libs = discover_libs()
    from build_dep_graph import find_lib_consumers

    lib_direct_consumers = find_lib_consumers(direct_libs) if direct_libs else set()
    for consumer in lib_direct_consumers:
        rel = consumer.replace("projects/", "", 1)
        direct_projects.add(rel)

    downstream = compute_downstream(direct_projects, direct_libs, schema_files, base)

    scripts_affected = find_affected_scripts(direct_libs)
    skills_affected = find_affected_skills(direct_libs)

    output = {
        "projects": sorted(direct_projects),
        "libs": sorted(direct_libs),
        "dbt": sorted(result["dbt"]),
        "global_changes": result["global_changes"],
        "downstream_affected": downstream,
        "scripts_affected": scripts_affected,
        "skills_affected": skills_affected,
    }

    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
