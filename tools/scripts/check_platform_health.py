"""
Platform health report — cross-references CODEOWNERS, data-architecture.md,
and the actual folders on disk.

Usage:
    uv run python tools/scripts/check_platform_health.py
    uv run python tools/scripts/check_platform_health.py --json
    make platform-health
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = ["apps", "libs", "dbt"]


# ── Data types ──────────────────────────────────────────────────────────────


@dataclass
class FolderStatus:
    path: str
    exists: bool
    in_codeowners: bool
    codeowners_pattern: str | None
    in_data_arch: bool
    has_agents_md: bool


@dataclass
class StaleEntry:
    source: str
    entry: str
    reason: str


@dataclass
class HealthReport:
    folders: list[FolderStatus] = field(default_factory=list)
    stale_codeowners: list[StaleEntry] = field(default_factory=list)
    stale_data_arch: list[StaleEntry] = field(default_factory=list)


# ── Parsers ──────────────────────────────────────────────────────────────────


def parse_codeowners(path: Path) -> tuple[list[str], list[str]]:
    """Return (wildcards, specific_paths) for apps/libs/dbt entries."""
    wildcards: list[str] = []
    specific: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if not parts:
            continue
        entry = parts[0].lstrip("/")
        if not any(entry.startswith(d + "/") for d in SCAN_DIRS):
            continue
        if "*" in entry or "?" in entry:
            wildcards.append(entry)
        else:
            specific.append(entry.rstrip("/"))
    return wildcards, specific


def parse_data_architecture(path: Path) -> list[str]:
    """Extract folder paths from the Project Catalogue table rows only."""
    folders: list[str] = []
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        # Only look inside the markdown table (skip header, separator, comments)
        if line.startswith("|") and "---" not in line and "Folder" not in line:
            in_table = True
        elif in_table and not line.startswith("|"):
            in_table = False

        if not in_table:
            continue

        # Match backtick-quoted paths with no wildcards: `apps/some-name`
        for match in re.finditer(r"`((?:apps|libs|dbt)/[^`*?]+)`", line):
            folders.append(match.group(1).rstrip("/"))
    return folders


def scan_disk() -> list[str]:
    """List all immediate subdirectories under apps/, libs/, dbt/."""
    found: list[str] = []
    for top in SCAN_DIRS:
        top_path = REPO_ROOT / top
        if not top_path.is_dir():
            continue
        for child in sorted(top_path.iterdir()):
            if child.is_dir():
                found.append(f"{top}/{child.name}")
    return found


# ── Matching ─────────────────────────────────────────────────────────────────


def codeowners_match(folder: str, wildcards: list[str]) -> str | None:
    """Return the first wildcard pattern that matches folder, or None."""
    for pattern in wildcards:
        # Strip trailing /* for fnmatch prefix matching
        clean = pattern.rstrip("/*")
        if fnmatch.fnmatch(folder, pattern) or folder.startswith(clean):
            return pattern
    return None


# ── Report builder ────────────────────────────────────────────────────────────


def build_report() -> HealthReport:
    report = HealthReport()

    codeowners_path = REPO_ROOT / "CODEOWNERS"
    data_arch_path = REPO_ROOT / "docs" / "data-architecture.md"

    wildcards, specific = parse_codeowners(codeowners_path)
    data_arch_folders = parse_data_architecture(data_arch_path)
    disk_folders = scan_disk()

    # All folders to evaluate = union of disk + specific CODEOWNERS + data-arch
    all_folders = sorted(
        set(disk_folders) | set(specific) | set(data_arch_folders)
    )

    for folder in all_folders:
        exists = (REPO_ROOT / folder).is_dir()
        in_co_specific = folder in specific
        co_pattern = codeowners_match(folder, wildcards) if not in_co_specific else folder
        in_co = in_co_specific or co_pattern is not None
        in_da = folder in data_arch_folders
        has_agents = (REPO_ROOT / folder / "AGENTS.md").is_file() if exists else False

        report.folders.append(
            FolderStatus(
                path=folder,
                exists=exists,
                in_codeowners=in_co,
                codeowners_pattern=co_pattern if in_co else None,
                in_data_arch=in_da,
                has_agents_md=has_agents,
            )
        )

    # Stale CODEOWNERS specific entries (folder doesn't exist on disk)
    for entry in specific:
        if not (REPO_ROOT / entry).is_dir():
            report.stale_codeowners.append(
                StaleEntry(
                    source="CODEOWNERS",
                    entry=entry,
                    reason="specific entry — folder does not exist on disk",
                )
            )

    # Stale data-architecture.md entries (folder doesn't exist on disk)
    for folder in data_arch_folders:
        if not (REPO_ROOT / folder).is_dir():
            report.stale_data_arch.append(
                StaleEntry(
                    source="data-architecture.md",
                    entry=folder,
                    reason="folder referenced in catalogue does not exist on disk",
                )
            )

    return report


# ── Formatters ────────────────────────────────────────────────────────────────


def icon(ok: bool) -> str:
    return "[OK]" if ok else "[!!]"


def print_report(report: HealthReport) -> int:
    from datetime import date

    SEP = "=" * 62
    DIV = "-" * 62
    print(f"\n{SEP}")
    print(f"  Platform Health Report -- {date.today()}")
    print(f"{SEP}\n")

    # Group by top-level dir
    for top in SCAN_DIRS:
        rows = [f for f in report.folders if f.path.startswith(top + "/")]
        print(DIV)
        print(f"  {top.upper()}/")
        print(DIV)

        if not rows:
            print("  (no folders)\n")
            continue

        header = f"  {'Folder':<32} {'Disk':^4} {'CODEOWNERS':^10} {'Data-Arch':^9} {'AGENTS.md':^9}"
        print(header)
        print(f"  {'-'*58}")

        for row in rows:
            name = row.path.split("/", 1)[1]
            print(
                f"  {name:<32} {icon(row.exists):^4}  "
                f"{icon(row.in_codeowners):^10}  "
                f"{icon(row.in_data_arch):^9}  "
                f"{icon(row.has_agents_md):^9}"
            )
        print()

    # Stale entries
    if report.stale_codeowners:
        print(DIV)
        print("  CODEOWNERS -- specific entries pointing to missing folders:")
        print(DIV)
        for s in report.stale_codeowners:
            print(f"  [!!]  /{s.entry}")
        print()

    if report.stale_data_arch:
        print(DIV)
        print("  data-architecture.md -- entries pointing to missing folders:")
        print(DIV)
        for s in report.stale_data_arch:
            print(f"  [!!]  {s.entry}")
        print()

    # Summary
    total = len(report.folders)
    issues = sum(
        1
        for f in report.folders
        if not f.exists or not f.in_codeowners or (
            f.path.startswith("apps/") and not f.in_data_arch
        ) or (f.exists and not f.has_agents_md)
    )
    stale = len(report.stale_codeowners) + len(report.stale_data_arch)

    print(SEP)
    print(f"  Folders tracked : {total}")
    print(f"  Issues          : {issues}")
    print(f"  Stale entries   : {stale}")
    status = "PASS" if issues == 0 and stale == 0 else "NEEDS ATTENTION"
    print(f"  Status          : {status}")
    print(f"{SEP}\n")

    return 1 if (issues > 0 or stale > 0) else 0


def print_json(report: HealthReport) -> int:
    data = {
        "folders": [
            {
                "path": f.path,
                "exists": f.exists,
                "in_codeowners": f.in_codeowners,
                "codeowners_pattern": f.codeowners_pattern,
                "in_data_arch": f.in_data_arch,
                "has_agents_md": f.has_agents_md,
            }
            for f in report.folders
        ],
        "stale_codeowners": [
            {"entry": s.entry, "reason": s.reason} for s in report.stale_codeowners
        ],
        "stale_data_arch": [
            {"entry": s.entry, "reason": s.reason} for s in report.stale_data_arch
        ],
    }
    print(json.dumps(data, indent=2))
    issues = sum(1 for f in report.folders if not f.exists or not f.in_codeowners)
    stale = len(report.stale_codeowners) + len(report.stale_data_arch)
    return 1 if (issues > 0 or stale > 0) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Platform health report")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        return print_json(report)
    return print_report(report)


if __name__ == "__main__":
    sys.exit(main())
