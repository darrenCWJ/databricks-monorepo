#!/usr/bin/env python3
"""Pre-commit hook: block imports across apps/ boundaries.

`apps/X` is allowed to import from `libs/*` but NOT from `apps/Y`.
This keeps deploy units independent and ownership clean.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def app_of(path: Path) -> str | None:
    """Return the app name if path is under apps/<name>/, else None."""
    try:
        rel = path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) >= 2 and parts[0] == "apps":
        return parts[1]
    return None


def check_file(path: Path) -> list[str]:
    """Return a list of error messages for cross-app imports in this file."""
    my_app = app_of(path)
    if my_app is None:
        return []
    tree = ast.parse(path.read_text())
    errs: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module.split(".")[0]
            # foreign app packages are named "<app>" with hyphens turned to underscores
            for app_dir in (REPO_ROOT / "apps").iterdir():
                if not app_dir.is_dir() or app_dir.name == my_app:
                    continue
                if mod == app_dir.name.replace("-", "_"):
                    errs.append(
                        f"{path}: imports from foreign app `{app_dir.name}` "
                        f"(from {node.module}). Use libs/* instead."
                    )
    return errs


def main(args: list[str]) -> int:
    all_errs: list[str] = []
    for a in args:
        all_errs.extend(check_file(Path(a)))
    if all_errs:
        print("\n".join(all_errs), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
