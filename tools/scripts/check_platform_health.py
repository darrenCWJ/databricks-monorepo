"""
Platform health report -- cross-references CODEOWNERS, data-architecture.md,
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
DEFAULT_OWNER = "@cdo/platform-team"


# ── Data types ───────────────────────────────────────────────────────────────


@dataclass
class FolderStatus:
    path: str
    exists: bool
    owners: list[str]
    in_codeowners: bool
    codeowners_pattern: str | None
    in_data_arch: bool
    has_agents_md: bool
    actions: list[str] = field(default_factory=list)


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


def parse_codeowners(path: Path) -> list[tuple[str, list[str]]]:
    """Return ordered list of (pattern, [owners]) for all lines.

    GitLab CODEOWNERS: later lines override earlier ones.
    """
    rules: list[tuple[str, list[str]]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern = parts[0].lstrip("/")
        owners = parts[1:]
        rules.append((pattern, owners))
    return rules


def resolve_owner(folder: str, rules: list[tuple[str, list[str]]]) -> tuple[list[str], str | None]:
    """Find the last matching CODEOWNERS rule for a folder.

    Returns (owners, matched_pattern). Falls back to DEFAULT_OWNER if no match.
    """
    matched_owners: list[str] = [DEFAULT_OWNER]
    matched_pattern: str | None = "*"
    for pattern, owners in rules:
        clean = pattern.rstrip("/*")
        if (
            fnmatch.fnmatch(folder, pattern)
            or fnmatch.fnmatch(folder + "/", pattern)
            or folder == clean
            or folder.startswith(clean + "/")
            or (pattern.endswith("*") and folder.startswith(clean))
        ):
            matched_owners = owners
            matched_pattern = pattern
    return matched_owners, matched_pattern


def folder_in_codeowners(folder: str, rules: list[tuple[str, list[str]]]) -> bool:
    """True if any rule explicitly covers this folder (not just the default *)."""
    for pattern, _ in rules:
        if pattern == "*":
            continue
        clean = pattern.rstrip("/*")
        if (
            fnmatch.fnmatch(folder, pattern)
            or fnmatch.fnmatch(folder + "/", pattern)
            or folder == clean
            or folder.startswith(clean + "/")
            or (pattern.endswith("*") and folder.startswith(clean))
        ):
            return True
    return False


def specific_entries(rules: list[tuple[str, list[str]]]) -> list[str]:
    """Return patterns that are specific folder paths (no wildcards)."""
    out: list[str] = []
    for pattern, _ in rules:
        entry = pattern.rstrip("/")
        if "*" not in entry and "?" not in entry and any(
            entry.startswith(d + "/") for d in SCAN_DIRS
        ):
            out.append(entry)
    return out


def parse_data_architecture(path: Path) -> list[str]:
    """Extract folder paths from the Project Catalogue table rows only."""
    folders: list[str] = []
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("|") and "---" not in line and "Folder" not in line:
            in_table = True
        elif in_table and not line.startswith("|"):
            in_table = False
        if not in_table:
            continue
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


# ── Action generator ─────────────────────────────────────────────────────────


def compute_actions(f: FolderStatus) -> list[str]:
    actions: list[str] = []
    if not f.exists:
        actions.append("Folder missing on disk -- create it or remove CODEOWNERS/data-arch entry")
    if not f.in_codeowners:
        actions.append("No owner assigned -- add explicit entry to CODEOWNERS")
    if f.path.startswith("apps/") and not f.in_data_arch:
        actions.append("Not in data catalogue -- fill AGENTS.md Inputs/Outputs, run `make data-map`")
    if f.exists and not f.has_agents_md:
        actions.append("No AGENTS.md -- create with Owner, Inputs, Outputs, Schedule, Rules")
    return actions


# ── Report builder ────────────────────────────────────────────────────────────


def build_report() -> HealthReport:
    report = HealthReport()

    codeowners_path = REPO_ROOT / "CODEOWNERS"
    data_arch_path = REPO_ROOT / "docs" / "data-architecture.md"

    rules = parse_codeowners(codeowners_path)
    specific = specific_entries(rules)
    data_arch_folders = parse_data_architecture(data_arch_path)
    disk_folders = scan_disk()

    all_folders = sorted(
        set(disk_folders) | set(specific) | set(data_arch_folders)
    )

    for folder in all_folders:
        exists = (REPO_ROOT / folder).is_dir()
        owners, pattern = resolve_owner(folder, rules)
        in_co = folder_in_codeowners(folder, rules)
        in_da = folder in data_arch_folders
        has_agents = (REPO_ROOT / folder / "AGENTS.md").is_file() if exists else False

        fs = FolderStatus(
            path=folder,
            exists=exists,
            owners=owners,
            in_codeowners=in_co,
            codeowners_pattern=pattern,
            in_data_arch=in_da,
            has_agents_md=has_agents,
        )
        fs.actions = compute_actions(fs)
        report.folders.append(fs)

    for entry in specific:
        if not (REPO_ROOT / entry).is_dir():
            report.stale_codeowners.append(
                StaleEntry(
                    source="CODEOWNERS",
                    entry=entry,
                    reason="specific entry -- folder does not exist on disk",
                )
            )

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


# ── Table helpers ─────────────────────────────────────────────────────────────


OK = "[OK]"
ERR = "[!!]"


def cell(ok: bool) -> str:
    return OK if ok else ERR


def row_has_issue(f: FolderStatus) -> bool:
    return bool(f.actions)


def _row(*cells: str, widths: list[int]) -> str:
    parts = [f" {c:<{w}} " for c, w in zip(cells, widths)]
    return "|" + "|".join(parts) + "|"


def _div(widths: list[int]) -> str:
    return "+" + "+".join("-" * (w + 2) for w in widths) + "+"


def _print_table(
    headers: list[str],
    rows: list[list[str]],
    widths: list[int],
    indent: str = "  ",
) -> None:
    d = indent + _div(widths)
    print(d)
    print(indent + _row(*headers, widths=widths))
    print(d)
    for r in rows:
        print(indent + _row(*r, widths=widths))
    print(d)


# ── Report printer ────────────────────────────────────────────────────────────


def print_report(report: HealthReport) -> int:
    from datetime import date

    SEP = "=" * 72
    total = len(report.folders)
    stale = len(report.stale_codeowners) + len(report.stale_data_arch)
    total_healthy = sum(1 for f in report.folders if not row_has_issue(f))
    issues = total - total_healthy
    status = "PASS" if issues == 0 and stale == 0 else "NEEDS ATTENTION"

    fw = max((len(f.path) for f in report.folders), default=20)
    fw = max(fw, 20)
    ow = max((len(", ".join(f.owners)) for f in report.folders), default=20)
    ow = max(ow, 18)

    print(f"\n{SEP}")
    print(f"  Platform Health Report -- {date.today()}")
    print(SEP)

    # ── TABLE 1: Overview by section ─────────────────────────────────────────
    print("\n  TABLE 1 -- OVERVIEW BY SECTION\n")
    t1_rows = []
    for top in SCAN_DIRS:
        grp = [f for f in report.folders if f.path.startswith(top + "/")]
        h = sum(1 for f in grp if not row_has_issue(f))
        t1_rows.append([f"{top}/", str(len(grp)), str(h), str(len(grp) - h)])
    t1_rows.append(["TOTAL", str(total), str(total_healthy), str(issues)])
    _print_table(
        ["Section", "Total", "Healthy", "Issues"],
        t1_rows,
        [10, 7, 9, 7],
    )

    # ── TABLE 2: Ownership summary by team ───────────────────────────────────
    print("\n  TABLE 2 -- OWNERSHIP SUMMARY BY TEAM\n")
    team_map: dict[str, list[FolderStatus]] = {}
    for f in report.folders:
        key = ", ".join(f.owners)
        team_map.setdefault(key, []).append(f)

    t2_rows = []
    for team, folders in sorted(team_map.items()):
        h = sum(1 for f in folders if not row_has_issue(f))
        folder_list = ", ".join(f.path for f in folders)
        t2_rows.append([team, str(len(folders)), str(h), str(len(folders) - h), folder_list])

    max_folders_col = max((len(r[4]) for r in t2_rows), default=20)
    max_folders_col = max(max_folders_col, 12)
    _print_table(
        ["Owner", "Total", "Healthy", "Issues", "Folders"],
        t2_rows,
        [ow, 7, 9, 7, max_folders_col],
    )

    # ── TABLE 3: Full detail per folder ──────────────────────────────────────
    print("\n  TABLE 3 -- FULL DETAIL PER FOLDER\n")
    t3_headers = ["Folder", "Owner", "Disk", "CODEOWNERS", "Data-Arch", "AGENTS.md"]
    t3_widths = [fw, ow, 6, 12, 11, 11]
    d3 = "  " + _div(t3_widths)
    print(d3)
    print("  " + _row(*t3_headers, widths=t3_widths))
    print(d3)
    prev_section = None
    for f in report.folders:
        section = f.path.split("/")[0]
        if prev_section is not None and section != prev_section:
            print(d3)
        prev_section = section
        print("  " + _row(
            f.path,
            ", ".join(f.owners),
            cell(f.exists),
            cell(f.in_codeowners),
            cell(f.in_data_arch),
            cell(f.has_agents_md),
            widths=t3_widths,
        ))
    print(d3)

    # ── TABLE 4: Actions required ─────────────────────────────────────────────
    action_folders = [f for f in report.folders if f.actions]
    if action_folders:
        print(f"\n  TABLE 4 -- ACTION REQUIRED ({len(action_folders)} folders)\n")
        aw = max((len(a) for f in action_folders for a in f.actions), default=40)
        aw = max(aw, 40)
        t4_widths = [fw, ow, aw]
        ad = "  " + _div(t4_widths)
        print(ad)
        print("  " + _row("Folder", "Owner", "Action", widths=t4_widths))
        print(ad)
        for f in action_folders:
            owner_str = ", ".join(f.owners)
            for i, action in enumerate(f.actions):
                folder_col = f.path if i == 0 else ""
                owner_col = owner_str if i == 0 else ""
                print("  " + _row(folder_col, owner_col, action, widths=t4_widths))
            print(ad)
    else:
        print("\n  TABLE 4 -- ACTION REQUIRED\n")
        print("  (none -- all folders are healthy)\n")

    # ── TABLE 5: Stale entries ────────────────────────────────────────────────
    all_stale = report.stale_codeowners + report.stale_data_arch
    if all_stale:
        print(f"\n  TABLE 5 -- STALE ENTRIES ({len(all_stale)})\n")
        rw = max((len(s.reason) for s in all_stale), default=40)
        rw = max(rw, 40)
        _print_table(
            ["Source", "Entry", "Reason"],
            [[s.source, s.entry, s.reason] for s in all_stale],
            [20, fw, rw],
        )

    # ── Legend ────────────────────────────────────────────────────────────────
    print("\n  LEGEND\n")
    _print_table(
        ["Column", "Passes [OK] when..."],
        [
            ["Disk",      "folder exists on disk"],
            ["CODEOWNERS","folder has an explicit rule (not just the default *)"],
            ["Data-Arch", "folder appears in docs/data-architecture.md (apps only)"],
            ["AGENTS.md", "AGENTS.md present with Owner, Inputs, Outputs, Schedule"],
            ["Healthy",   "ALL four checks above pass"],
            ["Issues",    "ANY one check fails -- see Table 4 for what to fix"],
        ],
        [12, 55],
    )

    # ── Footer ────────────────────────────────────────────────────────────────
    print(SEP)
    print(f"  Folders: {total}   Healthy: {total_healthy}   Issues: {issues}   Stale: {stale}")
    print(f"  Status : {status}")
    print(f"{SEP}\n")

    return 1 if (issues > 0 or stale > 0) else 0


def print_json(report: HealthReport) -> int:
    data = {
        "folders": [
            {
                "path": f.path,
                "exists": f.exists,
                "owners": f.owners,
                "in_codeowners": f.in_codeowners,
                "in_data_arch": f.in_data_arch,
                "has_agents_md": f.has_agents_md,
                "actions": f.actions,
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
    stale = len(report.stale_codeowners) + len(report.stale_data_arch)
    issues = sum(1 for f in report.folders if row_has_issue(f))
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
