#!/usr/bin/env python3
"""Build a unified dependency graph across the monorepo.

Parses three sources:
1. AGENTS.md — Inputs, Outputs, Runtime Dependencies sections
2. pyproject.toml — lib-to-lib and project-to-lib dependencies
3. contracts/schema.yml — output table column schemas

Usage:
    uv run python tools/scripts/build_dep_graph.py          # Print graph summary
    uv run python tools/scripts/build_dep_graph.py --json   # JSON output
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_agents_md_deps(path: Path) -> dict:
    """Extract Inputs, Outputs, and Runtime Dependencies from an AGENTS.md."""
    text = path.read_text(encoding="utf-8")
    result: dict = {"inputs": [], "outputs": [], "runtime_deps": []}
    current_section = None

    for line in text.splitlines():
        header = re.match(r"^## (.+)$", line)
        if header:
            section = header.group(1).strip().lower()
            if section == "inputs":
                current_section = "inputs"
            elif section == "outputs":
                current_section = "outputs"
            elif section in ("runtime dependencies", "runtime deps"):
                current_section = "runtime_deps"
            else:
                current_section = None
            continue

        if current_section and line.strip().startswith("- "):
            entry = line.strip()[2:].strip()
            if entry and not entry.startswith("("):
                result[current_section].append(entry)

    return result


def parse_table_ref(entry: str) -> str | None:
    """Extract a table name from an input/output entry.

    Handles formats like:
    - `${catalog}.silver.fct_orders` — description
    - cdo_dev.gold.payment_recon
    - table: customer_data.customer_360
    """
    entry = entry.strip("`")
    table_match = re.match(
        r"(?:table:\s*)?([a-zA-Z0-9_${}.*]+\.[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)", entry
    )
    if table_match:
        return table_match.group(1)
    return None


def parse_runtime_dep(entry: str) -> dict | None:
    """Parse a runtime dependency entry.

    Formats:
    - reads: projects/finance/sync-customer-360 (table: customer_data.customer_360)
    - calls: projects/finance/api-rates-service (endpoint: GET /rates/latest)
    - projects/finance/sync-customer-360 (table: customer_data.customer_360)
    """
    dep: dict = {"project": None, "type": "unknown", "detail": None}

    verb_match = re.match(r"(reads|calls|depends):\s*(.+)", entry)
    if verb_match:
        dep["type"] = verb_match.group(1)
        rest = verb_match.group(2)
    else:
        rest = entry

    proj_match = re.match(r"(projects/[^\s(]+)", rest)
    if proj_match:
        dep["project"] = proj_match.group(1)

    detail_match = re.search(r"\((.+)\)", rest)
    if detail_match:
        dep["detail"] = detail_match.group(1).strip()

    if dep["project"]:
        return dep
    return None


def discover_projects() -> dict[str, Path]:
    """Find all projects and return {relative_path: agents_md_path}."""
    projects: dict[str, Path] = {}
    projects_root = REPO_ROOT / "projects"
    if not projects_root.exists():
        return projects
    for agents_md in projects_root.glob("*/*/AGENTS.md"):
        rel = agents_md.parent.relative_to(REPO_ROOT)
        projects[str(rel)] = agents_md
    return projects


def discover_libs() -> dict[str, Path]:
    """Find all libs and return {name: pyproject_path}."""
    libs: dict[str, Path] = {}
    libs_root = REPO_ROOT / "libs"
    if not libs_root.exists():
        return libs
    for pyproj in libs_root.glob("*/pyproject.toml"):
        libs[pyproj.parent.name] = pyproj
    return libs


def parse_lib_deps(pyproject_path: Path) -> list[str]:
    """Extract dependency names from a pyproject.toml (simple text scan)."""
    text = pyproject_path.read_text()
    deps: list[str] = []
    in_deps = False
    for line in text.splitlines():
        if line.strip().startswith("dependencies"):
            in_deps = True
            continue
        if in_deps:
            if line.strip().startswith("]"):
                in_deps = False
                continue
            match = re.search(r'"([a-zA-Z0-9_-]+)', line)
            if match:
                deps.append(match.group(1))
    return deps


def build_lib_graph(libs: dict[str, Path]) -> dict[str, set[str]]:
    """Build lib->lib dependency edges. Returns {lib_name: set of lib deps}."""
    graph: dict[str, set[str]] = {}
    lib_names = set(libs.keys())
    for name, pyproj in libs.items():
        deps = parse_lib_deps(pyproj)
        graph[name] = {d for d in deps if d in lib_names}
    return graph


def transitive_closure(graph: dict[str, set[str]], start: set[str]) -> set[str]:
    """BFS through graph from start nodes, return all reachable nodes."""
    visited: set[str] = set()
    queue = list(start)
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        for dependent in graph.get(node, set()):
            if dependent not in visited:
                queue.append(dependent)
    return visited


def build_reverse_lib_graph(lib_graph: dict[str, set[str]]) -> dict[str, set[str]]:
    """Reverse: {lib_name: set of libs that depend on it}."""
    reverse: dict[str, set[str]] = defaultdict(set)
    for lib, deps in lib_graph.items():
        for dep in deps:
            reverse[dep].add(lib)
    return dict(reverse)


def find_lib_consumers(lib_names: set[str]) -> set[str]:
    """Find all projects that depend on any of the given lib names."""
    consumers: set[str] = set()
    projects_root = REPO_ROOT / "projects"
    if not projects_root.exists():
        return consumers
    for pyproj in projects_root.glob("*/*/pyproject.toml"):
        text = pyproj.read_text()
        for lib in lib_names:
            if lib in text:
                rel = pyproj.parent.relative_to(REPO_ROOT)
                consumers.add(str(rel))
                break
    return consumers


def all_transitive_lib_consumers(changed_libs: set[str], libs: dict[str, Path]) -> set[str]:
    """Given changed libs, find ALL affected projects via full transitive closure."""
    lib_graph = build_lib_graph(libs)
    reverse_graph = build_reverse_lib_graph(lib_graph)
    all_affected_libs = transitive_closure(reverse_graph, changed_libs)
    all_affected_libs |= changed_libs
    return find_lib_consumers(all_affected_libs)


def build_table_producer_map(projects: dict[str, Path]) -> dict[str, str]:
    """Map table_name -> project_path for all declared outputs."""
    table_to_project: dict[str, str] = {}
    for proj_path, agents_md in projects.items():
        deps = parse_agents_md_deps(agents_md)
        for output_entry in deps["outputs"]:
            table = parse_table_ref(output_entry)
            if table:
                table_to_project[table] = proj_path
    return table_to_project


def build_table_consumer_map(projects: dict[str, Path]) -> dict[str, set[str]]:
    """Map table_name -> set of project_paths that consume it."""
    table_consumers: dict[str, set[str]] = defaultdict(set)
    for proj_path, agents_md in projects.items():
        deps = parse_agents_md_deps(agents_md)
        for input_entry in deps["inputs"]:
            table = parse_table_ref(input_entry)
            if table:
                table_consumers[table].add(proj_path)
        for rt_entry in deps["runtime_deps"]:
            parsed = parse_runtime_dep(rt_entry)
            if parsed and parsed["detail"]:
                table_match = re.search(
                    r"table:\s*([a-zA-Z0-9_.${}]+\.[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)",
                    parsed["detail"],
                )
                if table_match:
                    table_consumers[table_match.group(1)].add(proj_path)
    return dict(table_consumers)


def build_runtime_dep_graph(projects: dict[str, Path]) -> dict[str, set[str]]:
    """Build project->project runtime dependency edges."""
    graph: dict[str, set[str]] = {}
    for proj_path, agents_md in projects.items():
        deps = parse_agents_md_deps(agents_md)
        runtime_targets: set[str] = set()
        for entry in deps["runtime_deps"]:
            parsed = parse_runtime_dep(entry)
            if parsed and parsed["project"]:
                runtime_targets.add(parsed["project"])
        if runtime_targets:
            graph[proj_path] = runtime_targets
    return graph


def build_reverse_runtime_graph(runtime_graph: dict[str, set[str]]) -> dict[str, set[str]]:
    """Reverse: {project: set of projects that depend on it at runtime}."""
    reverse: dict[str, set[str]] = defaultdict(set)
    for consumer, deps in runtime_graph.items():
        for dep in deps:
            reverse[dep].add(consumer)
    return dict(reverse)


def build_full_graph() -> dict:
    """Build the complete dependency graph."""
    projects = discover_projects()
    libs = discover_libs()

    lib_graph = build_lib_graph(libs)
    table_producers = build_table_producer_map(projects)
    table_consumers = build_table_consumer_map(projects)
    runtime_graph = build_runtime_dep_graph(projects)
    reverse_runtime = build_reverse_runtime_graph(runtime_graph)

    return {
        "projects": list(projects.keys()),
        "libs": list(libs.keys()),
        "lib_graph": {k: sorted(v) for k, v in lib_graph.items()},
        "table_producers": table_producers,
        "table_consumers": {k: sorted(v) for k, v in table_consumers.items()},
        "runtime_deps": {k: sorted(v) for k, v in runtime_graph.items()},
        "runtime_dependents": {k: sorted(v) for k, v in reverse_runtime.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    graph = build_full_graph()

    if args.json:
        json.dump(graph, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"Projects: {len(graph['projects'])}")
        print(f"Libraries: {len(graph['libs'])}")
        print(f"Tables tracked: {len(graph['table_producers'])}")
        print(f"Runtime dep edges: {sum(len(v) for v in graph['runtime_deps'].values())}")
        print()
        if graph["table_producers"]:
            print("Table producers:")
            for table, proj in sorted(graph["table_producers"].items()):
                consumers = graph["table_consumers"].get(table, [])
                print(f"  {table} <- {proj} -> consumed by {len(consumers)} project(s)")
        if graph["runtime_dependents"]:
            print("\nRuntime dependents:")
            for proj, deps in sorted(graph["runtime_dependents"].items()):
                print(f"  {proj} depended on by: {', '.join(sorted(deps))}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
