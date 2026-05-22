#!/usr/bin/env python3
"""Pre-commit hook: keep CODEOWNERS in sync with the rest of the repo.

Checks:
1. Every @cdo/<team> referenced outside CODEOWNERS also exists in CODEOWNERS.
2. Every group in CODEOWNERS is referenced at least once elsewhere
   (or appears in ALLOWED_UNREFERENCED — platform-wide / cross-cutting roles).
3. Every directory under apps/, libs/, dbt/ matches at least one CODEOWNERS rule.

Run manually:
    uv run python tools/scripts/check_ownership_sync.py
"""

from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SCAN_PATTERNS = [
    "AGENTS.md",
    "CLAUDE.md",
    "apps/*/AGENTS.md",
    "libs/*/AGENTS.md",
    "dbt/AGENTS.md",
    "dbt/*/AGENTS.md",
    "infra/**/*.tf",
    "databricks.yml",
    "docs/compliance/*.md",
    "docs/onboarding/*.md",
    "docs/runbooks/*.md",
    ".gitlab/merge_request_templates/*.md",
    "README.md",
]

# Files that intentionally contain example/illustrative group names
# (renamed teams in walkthroughs, etc.) — exclude from sync checks.
EXCLUDE_FILES = {
    "docs/runbooks/codeowners-maintenance.md",
}

GROUP_RE = re.compile(r"@cdo/[a-zA-Z0-9_-]+")

# Allowed groups that may exist in CODEOWNERS without being mentioned elsewhere
ALLOWED_UNREFERENCED = {
    "@cdo/platform-team",
    "@cdo/security",
    "@cdo/data-governance",
    "@cdo/analytics-eng-platform",
    "@cdo/restricted-cleared",
    "@cdo/customer-data",
    "@cdo/fraud-eng",
    "@cdo/infra-team",
    "@cdo/supplier-team",
    "@cdo/finance-team",
}


def scan_file(path: Path) -> set[str]:
    try:
        return set(GROUP_RE.findall(path.read_text(encoding="utf-8")))
    except Exception:
        return set()


def codeowners_lines() -> list[tuple[str, list[str]]]:
    """Parse CODEOWNERS into [(path_glob, [groups])]."""
    f = REPO_ROOT / "CODEOWNERS"
    if not f.exists():
        return []
    out: list[tuple[str, list[str]]] = []
    for line in f.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            out.append((parts[0], [p for p in parts[1:] if p.startswith("@")]))
    return out


def codeowners_groups(lines: list[tuple[str, list[str]]]) -> set[str]:
    g: set[str] = set()
    for _, gs in lines:
        g.update(gs)
    return g


def codeowners_path_globs(lines: list[tuple[str, list[str]]]) -> list[str]:
    return [glob for glob, _ in lines]


def referenced_groups() -> dict[str, list[Path]]:
    found: dict[str, list[Path]] = {}
    for pattern in SCAN_PATTERNS:
        for path in REPO_ROOT.glob(pattern):
            if not path.is_file():
                continue
            rel = path.relative_to(REPO_ROOT)
            if str(rel).replace("\\", "/") in EXCLUDE_FILES:
                continue
            for g in scan_file(path):
                found.setdefault(g, []).append(rel)
    return found


def matches_any_codeowners_glob(rel_path: str, globs: list[str]) -> bool:
    """Return True if rel_path is matched by at least one CODEOWNERS path glob."""
    if not rel_path.startswith("/"):
        rel_path = "/" + rel_path
    if not rel_path.endswith("/"):
        rel_path = rel_path + "/"
    for g in globs:
        if g == "*":
            continue  # default catch-all — every path matches but doesn't count
        if not g.startswith("/"):
            g = "/" + g
        if not g.endswith("/") and "*" not in g.split("/")[-1]:
            g = g + "/"
        if fnmatch.fnmatchcase(rel_path, g) or fnmatch.fnmatchcase(rel_path, g + "*"):
            return True
        # Also try the glob with trailing wildcard for prefix matches
        if fnmatch.fnmatchcase(rel_path[:-1], g[:-1]):
            return True
    return False


def directories_to_check() -> list[str]:
    """Each subdirectory of apps/, libs/, dbt/ must match a CODEOWNERS rule."""
    dirs: list[str] = []
    for top in ("apps", "libs", "dbt"):
        root = REPO_ROOT / top
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            if d.is_dir():
                dirs.append(f"{top}/{d.name}/")
    return dirs


def main() -> int:
    lines = codeowners_lines()
    co_groups = codeowners_groups(lines)
    co_globs = codeowners_path_globs(lines)
    refs = referenced_groups()
    errs: list[str] = []
    warns: list[str] = []

    # Check 1: every referenced group must exist in CODEOWNERS
    for g, files in refs.items():
        if g not in co_groups:
            errs.append(
                f"Group {g} referenced in {len(files)} file(s) "
                f"({', '.join(str(f) for f in files[:3])}) "
                f"but NOT declared in CODEOWNERS."
            )

    # Check 2: every group in CODEOWNERS should be referenced or allowlisted
    for g in co_groups - set(refs.keys()):
        if g not in ALLOWED_UNREFERENCED:
            warns.append(f"Group {g} declared in CODEOWNERS but referenced nowhere else.")

    # Check 3: every apps/, libs/, dbt/ directory must match a CODEOWNERS rule
    for d in directories_to_check():
        if not matches_any_codeowners_glob(d, co_globs):
            errs.append(f"Directory /{d} has no specific CODEOWNERS rule (falls to default).")

    if warns:
        print("WARNINGS:", file=sys.stderr)
        for w in warns:
            print(f"  - {w}", file=sys.stderr)

    if errs:
        print("ERRORS:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        print(
            "\nFix: update CODEOWNERS (see docs/runbooks/codeowners-maintenance.md)",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: {len(co_groups)} groups in CODEOWNERS, "
        f"{len(refs)} groups referenced elsewhere, "
        f"{len(directories_to_check())} dirs covered."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
