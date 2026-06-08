#!/usr/bin/env python3
"""CI lint: verify projects declare lib dependencies in pyproject.toml.

Scans all Python files under projects/ for imports from libs/ packages.
If a project imports a lib but does not declare it in its pyproject.toml,
this check fails with a clear error.

This ensures `make affected` can detect blast radius when libs change.

Usage:
    uv run python tools/scripts/check_lib_deps.py
    uv run python tools/scripts/check_lib_deps.py --fix  # print fix instructions

Exit codes:
    0 — all lib imports are declared
    1 — undeclared lib imports found
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def discover_lib_packages() -> set[str]:
    """Find all importable package names under libs/."""
    libs_root = REPO_ROOT / "libs"
    if not libs_root.exists():
        return set()
    return {d.name for d in libs_root.iterdir() if d.is_dir() and (d / "__init__.py").exists()}


def get_project_declared_deps(pyproject_path: Path) -> set[str]:
    """Extract dependency names from a project's pyproject.toml."""
    if not pyproject_path.exists():
        return set()
    text = pyproject_path.read_text()
    deps: set[str] = set()
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("dependencies"):
            in_deps = True
            continue
        if in_deps:
            if stripped.startswith("]"):
                break
            if '"' in stripped:
                name = stripped.split('"')[1].split(">=")[0].split("==")[0].split("<")[0].strip()
                deps.add(name)
                deps.add(name.replace("-", "_"))
    return deps


def find_lib_imports_in_file(path: Path, lib_packages: set[str]) -> set[str]:
    """Find which lib packages are imported in a Python file."""
    try:
        tree = ast.parse(path.read_text())
    except (SyntaxError, UnicodeDecodeError):
        return set()

    imported_libs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_module = alias.name.split(".")[0]
                if top_module in lib_packages:
                    imported_libs.add(top_module)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_module = node.module.split(".")[0]
            if top_module in lib_packages:
                imported_libs.add(top_module)

    return imported_libs


def project_of(path: Path) -> tuple[str, Path] | None:
    """Return (project_name, project_root) if path is under projects/."""
    try:
        rel = path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) >= 3 and parts[0] == "projects":
        project_name = f"{parts[1]}/{parts[2]}"
        project_root = REPO_ROOT / "projects" / parts[1] / parts[2]
        return project_name, project_root
    return None


def main() -> int:
    lib_packages = discover_lib_packages()
    if not lib_packages:
        return 0

    projects_root = REPO_ROOT / "projects"
    if not projects_root.exists():
        return 0

    errors: list[str] = []
    checked_projects: dict[str, set[str]] = {}

    for py_file in projects_root.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        result = project_of(py_file)
        if not result:
            continue

        project_name, project_root = result
        imported_libs = find_lib_imports_in_file(py_file, lib_packages)

        if not imported_libs:
            continue

        if project_name not in checked_projects:
            pyproject = project_root / "pyproject.toml"
            checked_projects[project_name] = get_project_declared_deps(pyproject)

        declared = checked_projects[project_name]

        for lib in imported_libs:
            lib_hyphen = lib.replace("_", "-")
            if lib not in declared and lib_hyphen not in declared:
                rel_path = py_file.relative_to(REPO_ROOT)
                errors.append(
                    f"  {rel_path}: imports '{lib}' but "
                    f"projects/{project_name}/pyproject.toml does not declare it.\n"
                    f'    Fix: add "{lib_hyphen}" to [project] dependencies'
                )

    if errors:
        print("ERROR: Undeclared library dependencies found.\n")
        print("Projects that import from libs/ must declare the dependency in")
        print("their pyproject.toml so `make affected` can track blast radius.\n")
        for err in sorted(set(errors)):
            print(err)
        print(f"\n{len(errors)} undeclared import(s) found.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
