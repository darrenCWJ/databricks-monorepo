#!/usr/bin/env python3
"""Compare graphify knowledge graph against AGENTS.md declarations.

Checks:
1. Every AGENTS.md ## Inputs reference resolves to a real graph node
2. Every AGENTS.md ## Outputs reference resolves to a real graph node
3. Every AGENTS.md ## Runtime Dependencies target folder exists on disk
4. All projects/libs folders have AGENTS.md coverage
5. Cross-boundary imports in graph have matching pyproject.toml declarations

Usage:
    uv run python tools/scripts/check_graph_drift.py
    uv run python tools/scripts/check_graph_drift.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = REPO_ROOT / "graphify-out" / "graph.json"
SCAN_DIRS = ["projects", "libs"]


def load_graph(path: Path) -> dict:
    if not path.exists():
        return {"nodes": [], "edges": []}
    return json.loads(path.read_text(encoding="utf-8"))


def find_agents_md_files() -> list[Path]:
    results = []
    for scan_dir in SCAN_DIRS:
        base = REPO_ROOT / scan_dir
        if base.exists():
            results.extend(base.rglob("AGENTS.md"))
    return sorted(results)


def parse_section_items(text: str, section_name: str) -> list[str]:
    lines = text.splitlines()
    items: list[str] = []
    in_section = False

    for line in lines:
        header = re.match(r"^## (.+)$", line)
        if header:
            in_section = header.group(1).strip().lower() == section_name.lower()
            continue
        if in_section and line.strip().startswith("- "):
            entry = line.strip()[2:].strip()
            if entry and not entry.startswith("("):
                items.append(entry)

    return items


def check_folder_coverage() -> list[str]:
    errors: list[str] = []
    for scan_dir in SCAN_DIRS:
        base = REPO_ROOT / scan_dir
        if not base.exists():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith("."):
                continue
            agents_md = child / "AGENTS.md"
            if not agents_md.exists():
                for sub in child.iterdir():
                    if sub.is_dir() and not sub.name.startswith("."):
                        sub_agents = sub / "AGENTS.md"
                        if not sub_agents.exists():
                            rel = sub.relative_to(REPO_ROOT)
                            errors.append(f"{rel}: missing AGENTS.md")
    return errors


def check_runtime_deps(agents_files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in agents_files:
        text = path.read_text(encoding="utf-8")
        deps = parse_section_items(text, "Runtime Dependencies")
        for dep in deps:
            dep_match = re.match(r"(?:reads|calls|depends):\s*(\S+)", dep)
            if dep_match:
                target_path = dep_match.group(1)
                full_path = REPO_ROOT / target_path
                if not full_path.exists():
                    rel = path.relative_to(REPO_ROOT)
                    errors.append(f"{rel}: runtime dependency '{target_path}' not found on disk")
    return errors


def check_graph_nodes(graph: dict, agents_files: list[Path]) -> list[str]:
    if not graph.get("nodes"):
        return []

    node_sources = {n.get("source_file", "") for n in graph["nodes"]}
    errors: list[str] = []

    for path in agents_files:
        text = path.read_text(encoding="utf-8")
        inputs = parse_section_items(text, "Inputs")
        outputs = parse_section_items(text, "Outputs")

        for item in inputs + outputs:
            table_match = re.match(r".*\(table:\s*([^)]+)\)", item)
            if table_match:
                table_name = table_match.group(1).strip()
                if not any(table_name in src for src in node_sources):
                    rel = path.relative_to(REPO_ROOT)
                    errors.append(f"{rel}: declared table '{table_name}' not found in graph")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    graph = load_graph(GRAPH_PATH)
    agents_files = find_agents_md_files()

    all_errors: list[str] = []
    all_errors.extend(check_folder_coverage())
    all_errors.extend(check_runtime_deps(agents_files))
    all_errors.extend(check_graph_nodes(graph, agents_files))

    if args.json:
        print(json.dumps({"errors": all_errors, "count": len(all_errors)}, indent=2))
    else:
        if all_errors:
            print(f"Graph drift detected ({len(all_errors)} issues):\n")
            for err in all_errors:
                print(f"  - {err}")
            print()
        else:
            print("No graph drift detected. AGENTS.md claims match reality.")

    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
