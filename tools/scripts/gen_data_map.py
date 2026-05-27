"""Generate docs/data-architecture.md from per-app AGENTS.md declarations.

Reads ## Inputs, ## Outputs, ## Owner, and ## Schedule sections from each
apps/*/AGENTS.md file and produces a cross-project dependency map.

Usage:
    python gen_data_map.py           # Write docs/data-architecture.md
    python gen_data_map.py --check   # Exit non-zero if file is out of date
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def parse_agents_md(path: Path) -> dict:
    """Extract structured sections from an AGENTS.md file."""
    text = path.read_text()
    lines = text.splitlines()

    result = {
        "name": "",
        "folder": str(path.parent.relative_to(path.parent.parent.parent)),
        "owner": "",
        "inputs": [],
        "outputs": [],
        "schedule": "",
    }

    if lines and lines[0].startswith("# "):
        result["name"] = lines[0][2:].strip()

    current_section = None
    for line in lines:
        header_match = re.match(r"^## (.+)$", line)
        if header_match:
            current_section = header_match.group(1).strip().lower()
            continue

        if current_section == "inputs" and line.strip().startswith("- "):
            entry = line.strip()[2:].strip()
            if entry and not entry.startswith("("):
                result["inputs"].append(entry)
        elif current_section == "outputs" and line.strip().startswith("- "):
            entry = line.strip()[2:].strip()
            if entry and not entry.startswith("("):
                result["outputs"].append(entry)
        elif current_section == "owner" and line.strip():
            result["owner"] = line.strip()
            current_section = None
        elif current_section == "schedule" and line.strip():
            if not line.strip().startswith("TODO"):
                result["schedule"] = line.strip()
            current_section = None

    return result


def extract_source_app(input_entry: str) -> str:
    """Extract the source app/project name from an input entry like 'cdo.silver.fct_orders (platform-core)'."""
    match = re.search(r"\(([^)]+)\)", input_entry)
    return match.group(1) if match else ""


def generate_data_architecture(repo_root: Path) -> str:
    """Generate the full data-architecture.md content."""
    apps_dir = repo_root / "apps"
    if not apps_dir.exists():
        return "# Data Architecture\n\nNo apps/ directory found.\n"

    projects = []
    for agents_md in sorted(apps_dir.glob("*/AGENTS.md")):
        parsed = parse_agents_md(agents_md)
        if parsed["name"]:
            projects.append(parsed)

    lines = [
        "# Data Architecture",
        "",
        "Auto-generated from `apps/*/AGENTS.md`. Do not edit manually.",
        "Regenerate with: `make data-map`",
        "",
        "## Project Catalogue",
        "",
        "| Project | Folder | Owner | Reads from | Writes to | Schedule |",
        "|---------|--------|-------|------------|-----------|----------|",
    ]

    for p in projects:
        reads = ", ".join(p["inputs"]) if p["inputs"] else "—"
        writes = ", ".join(p["outputs"]) if p["outputs"] else "—"
        schedule = p["schedule"] if p["schedule"] else "—"
        lines.append(
            f"| {p['name']} | `{p['folder']}` | {p['owner']} | {reads} | {writes} | {schedule} |"
        )

    app_names = {p["name"] for p in projects}
    external_sources = set()

    for p in projects:
        for inp in p["inputs"]:
            source = extract_source_app(inp)
            if source and source not in app_names:
                external_sources.add(source)

    # Cross-project matrix: only apps that exist in apps/
    if len(projects) > 1:
        producers = sorted(app_names)
        has_internal_deps = any(
            extract_source_app(inp) in app_names for p in projects for inp in p["inputs"]
        )

        if has_internal_deps:
            lines.extend(
                [
                    "",
                    "## Cross-Project Read Matrix",
                    "",
                    "Apps in this repo only. A dot means the row reads from the column.",
                    "",
                ]
            )

            header = "| Consumer | " + " | ".join(producers) + " |"
            separator = "|----------|" + "|".join(["---"] * len(producers)) + "|"
            lines.append(header)
            lines.append(separator)

            for p in projects:
                sources = {
                    extract_source_app(inp) for inp in p["inputs"] if extract_source_app(inp)
                }
                cells = [" . " if prod in sources else "   " for prod in producers]
                lines.append(f"| {p['name']} | " + "|".join(cells) + "|")

    # External sources not in this repo
    if external_sources:
        lines.extend(
            [
                "",
                "## External Sources",
                "",
                "Referenced in Inputs but not managed in `apps/`:",
                "",
            ]
        )
        for source in sorted(external_sources):
            lines.append(f"- {source}")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if docs/data-architecture.md is out of date",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (auto-detected if not given)",
    )
    args = parser.parse_args()

    if args.repo_root:
        repo_root = args.repo_root
    else:
        repo_root = Path(__file__).resolve().parent.parent.parent

    output_path = repo_root / "docs" / "data-architecture.md"
    generated = generate_data_architecture(repo_root)

    if args.check:
        if not output_path.exists():
            print(f"FAIL: {output_path} does not exist. Run `make data-map` to generate it.")
            return 1

        current = output_path.read_text()
        if current != generated:
            print(f"FAIL: {output_path} is out of date.")
            print("Run `make data-map` to regenerate it.")
            return 1

        print(f"OK: {output_path} is up to date.")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generated)
    print(f"Generated {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
