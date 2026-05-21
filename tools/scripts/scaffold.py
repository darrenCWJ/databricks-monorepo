#!/usr/bin/env python3
"""Scaffold new apps and libs from templates.

Usage:
    uv run python tools/scripts/scaffold.py app --name my-pipeline --kind python
    uv run python tools/scripts/scaffold.py app --name my-stream --kind scala
    uv run python tools/scripts/scaffold.py lib --name common-utils
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from textwrap import dedent

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        print(f"  skip (exists): {path.relative_to(REPO_ROOT)}")
        return
    path.write_text(content.lstrip("\n"))
    print(f"  + {path.relative_to(REPO_ROOT)}")


def scaffold_python_app(name: str) -> None:
    pkg = name.replace("-", "_")
    root = REPO_ROOT / "apps" / name
    print(f"Scaffolding Python DAB: {root.relative_to(REPO_ROOT)}")
    _write(root / "AGENTS.md", f"# {name}\n\nTODO: describe what this bundle does.\n\n## Owner\n@cdo/TODO-team\n\n## Inputs\n- (declare tables this app reads from)\n\n## Outputs\n- (declare tables this app writes to)\n\n## Schedule\nTODO\n\n## Rules\n- (app-specific rules)\n")
    _write(root / "bundle.yml", dedent(f"""
        resources:
          jobs:
            {pkg}_daily:
              name: {name}-${{bundle.target}}
              tags: {{ bundle: {name} }}
              tasks:
                - task_key: run
                  notebook_task:
                    notebook_path: ./notebooks/run.py
                    base_parameters: {{ catalog: ${{var.catalog}} }}
    """))
    _write(root / "pyproject.toml", dedent(f"""
        [project]
        name = "{name}"
        version = "0.1.0"
        requires-python = ">=3.11"
        dependencies = ["pyspark>=3.5", "common-spark"]

        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [tool.hatch.build.targets.wheel]
        packages = ["src/{pkg}"]
    """))
    _write(root / f"src/{pkg}/__init__.py", "")
    _write(root / f"src/{pkg}/job.py", dedent(f'''
        """Top-level job entry points."""

        def run(catalog: str) -> None:
            """TODO: implement."""
            print(f"hello from {{catalog}}")
    '''))
    _write(root / "tests/test_job.py", dedent(f"""
        import pytest
        from {pkg}.job import run

        @pytest.mark.unit
        def test_run_smoke(capsys) -> None:
            run("cdo_dev")
            assert "hello from cdo_dev" in capsys.readouterr().out
    """))
    _write(root / "notebooks/run.py", dedent(f"""
        # Databricks notebook source
        dbutils.widgets.text("catalog", "cdo_dev")
        catalog = dbutils.widgets.get("catalog")
        from {pkg}.job import run
        run(catalog)
    """))


def scaffold_scala_app(name: str) -> None:
    root = REPO_ROOT / "apps" / name
    print(f"Scaffolding Scala DAB: {root.relative_to(REPO_ROOT)}")
    _write(root / "AGENTS.md", f"# {name}\n\nTODO: describe what this bundle does.\n\n## Owner\n@cdo/TODO-team\n\n## Inputs\n- (declare tables this app reads from)\n\n## Outputs\n- (declare tables this app writes to)\n\n## Schedule\nTODO\n\n## Rules\n- (app-specific rules)\n")
    _write(root / "bundle.yml", dedent(f"""
        resources:
          jobs:
            {name.replace('-', '_')}:
              name: {name}-${{bundle.target}}
              tags: {{ bundle: {name} }}
              tasks:
                - task_key: run
                  spark_jar_task:
                    main_class_name: com.cdo.{name.replace('-', '')}.App
                  libraries:
                    - jar: ./target/scala-2.12/{name}-assembly-0.1.0.jar
    """))
    _write(root / "build.sbt", dedent(f"""
        name := "{name}"
        version := "0.1.0"
        scalaVersion := "2.12.18"
        libraryDependencies += "org.apache.spark" %% "spark-sql" % "3.5.1" % "provided"
        libraryDependencies += "org.scalatest" %% "scalatest" % "3.2.18" % Test
    """))
    _write(root / "project/build.properties", "sbt.version=1.10.1\n")
    pkg = name.replace("-", "")
    _write(root / f"src/main/scala/com/cdo/{pkg}/App.scala", dedent(f"""
        package com.cdo.{pkg}
        object App {{
          def main(args: Array[String]): Unit = println("hello from {name}")
        }}
    """))


def scaffold_lib(name: str) -> None:
    pkg = name.replace("-", "_")
    root = REPO_ROOT / "libs" / name
    print(f"Scaffolding lib: {root.relative_to(REPO_ROOT)}")
    _write(root / "AGENTS.md", f"# {name}\n\nTODO: purpose and public API.\n")
    _write(root / "pyproject.toml", dedent(f"""
        [project]
        name = "{name}"
        version = "0.1.0"
        requires-python = ">=3.11"
        dependencies = []

        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [tool.hatch.build.targets.wheel]
        packages = ["src/{pkg}"]
    """))
    _write(root / f"src/{pkg}/__init__.py", f'"""{name} — shared lib."""\n')
    _write(root / "tests/test_smoke.py", "def test_smoke(): pass\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="kind", required=True)
    app = sub.add_parser("app")
    app.add_argument("--name", required=True)
    app.add_argument("--kind", choices=["python", "scala"], default="python")
    lib = sub.add_parser("lib")
    lib.add_argument("--name", required=True)
    args = parser.parse_args()
    if args.kind in ("python",) and parser.parse_args().__class__.__name__:
        pass
    if args.kind == "python":
        scaffold_python_app(args.name)
    elif args.kind == "scala":
        scaffold_scala_app(args.name)
    elif args.kind is None:  # lib subcommand path
        scaffold_lib(args.name)
    else:
        # subparser was 'lib'
        scaffold_lib(args.name)
    print("Done. Remember to add the new package to pyproject.toml [tool.uv.workspace] members.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
