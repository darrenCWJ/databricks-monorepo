"""
Discover available shared libraries and what they provide.

Scans libs/*/AGENTS.md and surfaces the Provides section of each lib
so engineers know what is available before writing new code.

Usage:
    uv run python tools/scripts/list_libs.py
    uv run python tools/scripts/list_libs.py --keyword finance
    make list-libs
    make list-libs KEYWORD=validation
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class LibInfo:
    name: str
    path: str
    owner: str
    description: str
    provides: list[str] = field(default_factory=list)
    consumers: list[str] = field(default_factory=list)
    has_agents_md: bool = True


def parse_lib_agents_md(agents_path: Path) -> LibInfo:
    name = agents_path.parent.name
    path = f"libs/{name}"
    text = agents_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    owner = "@cdo/platform-team"
    description = ""
    provides: list[str] = []
    consumers: list[str] = []

    current_section: str | None = None
    desc_lines: list[str] = []
    past_header = False

    for line in lines:
        stripped = line.strip()

        # Section headings
        if re.match(r"^## (.+)", stripped):
            section = re.match(r"^## (.+)", stripped).group(1).lower()
            current_section = section
            past_header = True
            continue

        # Top-level header — skip
        if stripped.startswith("# "):
            continue

        if current_section == "owner":
            if stripped.startswith("@"):
                owner = stripped
        elif current_section == "provides":
            if stripped.startswith("-"):
                provides.append(stripped.lstrip("- ").strip())
        elif current_section == "consumers":
            if stripped.startswith("-"):
                consumers.append(stripped.lstrip("- ").strip())
        elif current_section is None and past_header is False:
            # Description paragraph before first section
            if stripped:
                desc_lines.append(stripped)
        elif current_section is None and not stripped.startswith("##"):
            if stripped:
                desc_lines.append(stripped)

    # Grab description: first non-empty paragraph before any ## section
    raw = text
    before_first_section = re.split(r"\n## ", raw)[0]
    paras = [p.strip() for p in before_first_section.split("\n\n") if p.strip()]
    # Skip the h1 title line
    desc_paras = [p for p in paras if not p.startswith("#")]
    description = desc_paras[0] if desc_paras else ""

    return LibInfo(
        name=name,
        path=path,
        owner=owner,
        description=description,
        provides=provides,
        consumers=consumers,
    )


def scan_libs(keyword: str | None = None) -> list[LibInfo]:
    libs_root = REPO_ROOT / "libs"
    if not libs_root.is_dir():
        return []

    results: list[LibInfo] = []
    for child in sorted(libs_root.iterdir()):
        if not child.is_dir():
            continue
        agents_path = child / "AGENTS.md"
        if not agents_path.is_file():
            results.append(
                LibInfo(
                    name=child.name,
                    path=f"libs/{child.name}",
                    owner="@cdo/platform-team",
                    description="(no AGENTS.md — run `make new-lib` to scaffold)",
                    has_agents_md=False,
                )
            )
            continue
        info = parse_lib_agents_md(agents_path)
        results.append(info)

    if keyword:
        kw = keyword.lower()
        results = [
            lib for lib in results
            if kw in lib.name.lower()
            or kw in lib.description.lower()
            or any(kw in p.lower() for p in lib.provides)
        ]

    return results


SEP = "=" * 72
OK = "[OK]"
WARN = "[!!]"


def _div(widths: list[int]) -> str:
    return "+" + "+".join("-" * (w + 2) for w in widths) + "+"


def _row(*cells: str, widths: list[int]) -> str:
    parts = [f" {c:<{w}} " for c, w in zip(cells, widths)]
    return "|" + "|".join(parts) + "|"


def print_report(libs: list[LibInfo], keyword: str | None) -> int:
    from datetime import date

    print(f"\n{SEP}")
    title = "Available Shared Libraries"
    if keyword:
        title += f" (filter: '{keyword}')"
    print(f"  {title} -- {date.today()}")
    print(SEP)

    if not libs:
        if keyword:
            print(f"\n  No libs matched keyword '{keyword}'.\n")
        else:
            print("\n  No libs found under libs/.\n")
            print("  Create one with: make new-lib NAME=<team>-common\n")
        print(SEP + "\n")
        return 0

    # ── Overview table ────────────────────────────────────────────────────────
    print("\n  AVAILABLE LIBS\n")
    nw = max(len(lib.name) for lib in libs)
    nw = max(nw, 12)
    ow = max(len(lib.owner) for lib in libs)
    ow = max(ow, 10)
    pw = max(
        (len(f"{len(lib.provides)} item(s)") for lib in libs),
        default=10,
    )
    pw = max(pw, 10)
    dw = max(min(len(lib.description), 50) for lib in libs)
    dw = max(dw, 20)

    d = "  " + _div([nw, ow, pw, dw])
    print(d)
    print("  " + _row("Library", "Owner", "Provides", "Description", widths=[nw, ow, pw, dw]))
    print(d)
    for lib in libs:
        desc_short = lib.description[:50] + "..." if len(lib.description) > 50 else lib.description
        provides_count = f"{len(lib.provides)} item(s)" if lib.provides else "(none documented)"
        print("  " + _row(lib.name, lib.owner, provides_count, desc_short, widths=[nw, ow, pw, dw]))
    print(d)

    # ── Detail per lib ────────────────────────────────────────────────────────
    for lib in libs:
        print(f"\n  {lib.path}")
        print(f"  {'─' * (len(lib.path) + 2)}")
        print(f"  Owner  : {lib.owner}")
        if lib.description:
            print(f"  About  : {lib.description}")
        if lib.consumers:
            print(f"  Used by: {', '.join(lib.consumers)}")
        if lib.provides:
            print("  Provides:")
            for item in lib.provides:
                print(f"    - {item}")
        else:
            print("  Provides: (none documented — add a ## Provides section to AGENTS.md)")
        print(f"  Import : from {lib.name.replace('-', '_')} import ...")
        print(f"  Add dep: uv add {lib.name} --package apps/<your-app>")

    # ── Footer ────────────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print(f"  Libs available: {len(libs)}")
    print(f"  Tip: run `make list-libs KEYWORD=<term>` to filter by topic")
    print(f"{SEP}\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="List available shared libraries")
    parser.add_argument("--keyword", "-k", help="Filter libs by keyword (name, description, provides)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    libs = scan_libs(keyword=args.keyword)

    if args.json:
        import json
        data = [
            {
                "name": lib.name,
                "path": lib.path,
                "owner": lib.owner,
                "description": lib.description,
                "provides": lib.provides,
                "consumers": lib.consumers,
                "has_agents_md": lib.has_agents_md,
            }
            for lib in libs
        ]
        print(json.dumps(data, indent=2))
        return 0

    return print_report(libs, keyword=args.keyword)


if __name__ == "__main__":
    sys.exit(main())
