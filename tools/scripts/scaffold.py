#!/usr/bin/env python3
"""Scaffold new projects and libs from templates.

Usage:
    uv run python tools/scripts/scaffold.py project --domain finance --function pipeline --name accounts-payable --kind python
    uv run python tools/scripts/scaffold.py project --domain hcm --function streaming --name employee-events --kind scala
    uv run python tools/scripts/scaffold.py project --domain finance --function app --name budget-viewer --kind python
    uv run python tools/scripts/scaffold.py lib --name common-utils
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from textwrap import dedent

REPO_ROOT = Path(__file__).resolve().parents[2]

VALID_FUNCTIONS = [
    "pipeline",
    "streaming",
    "app",
    "dashboard",
    "api",
    "sync",
    "capture",
]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        print(f"  skip (exists): {path.relative_to(REPO_ROOT)}")
        return
    path.write_text(content.lstrip("\n"))
    print(f"  + {path.relative_to(REPO_ROOT)}")


def _common_agents_md(name: str, function: str, domain: str) -> str:
    return (
        f"# {name}\n\n"
        f"TODO: describe what this {function} does.\n\n"
        f"## Owner\n@wei_hao_tan @jeffrey_siew\n\n"
        f"## Domain\n{domain}\n\n"
        f"## Function\n{function}\n\n"
        f"## Inputs\n- (declare tables/sources this project reads from)\n\n"
        f"## Outputs\n- (declare tables/endpoints this project writes to)\n\n"
        f"## Schedule\nTODO\n\n"
        f"## Rules\n- (project-specific rules)\n"
    )


def scaffold_pipeline(domain: str, name: str, kind: str) -> None:
    dir_name = f"pipeline-{name}"
    pkg = dir_name.replace("-", "_")
    root = REPO_ROOT / "projects" / domain / dir_name
    print(f"Scaffolding pipeline ({kind}): {root.relative_to(REPO_ROOT)}")

    _write(root / "AGENTS.md", _common_agents_md(dir_name, "pipeline", domain))

    if kind == "python":
        _write(
            root / "bundle.yml",
            dedent(f"""
            resources:
              jobs:
                {pkg}_daily:
                  name: {dir_name}-${{bundle.target}}
                  tags: {{ bundle: {dir_name}, domain: {domain} }}
                  tasks:
                    - task_key: run
                      notebook_task:
                        notebook_path: ./notebooks/run.py
                        base_parameters: {{ catalog: ${{var.catalog}} }}
        """),
        )
        _write(
            root / "pyproject.toml",
            dedent(f"""
            [project]
            name = "{dir_name}"
            version = "0.1.0"
            requires-python = ">=3.11"
            dependencies = ["pyspark>=3.5"]

            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [tool.hatch.build.targets.wheel]
            packages = ["src/{pkg}"]
        """),
        )
        _write(root / f"src/{pkg}/__init__.py", "")
        _write(
            root / f"src/{pkg}/job.py",
            dedent('''
            """Top-level job entry points."""

            def run(catalog: str) -> None:
                """TODO: implement."""
                print(f"hello from {catalog}")
        '''),
        )
        _write(
            root / "tests/test_job.py",
            dedent(f"""
            import pytest
            from {pkg}.job import run

            @pytest.mark.unit
            def test_run_smoke(capsys) -> None:
                run("cdo_dev")
                assert "hello from cdo_dev" in capsys.readouterr().out
        """),
        )
        _write(
            root / "notebooks/run.py",
            dedent(f"""
            # Databricks notebook source
            dbutils.widgets.text("catalog", "cdo_dev")
            catalog = dbutils.widgets.get("catalog")
            from {pkg}.job import run
            run(catalog)
        """),
        )
    elif kind == "scala":
        scala_pkg = dir_name.replace("-", "")
        _write(
            root / "bundle.yml",
            dedent(f"""
            resources:
              jobs:
                {pkg}:
                  name: {dir_name}-${{bundle.target}}
                  tags: {{ bundle: {dir_name}, domain: {domain} }}
                  tasks:
                    - task_key: run
                      spark_jar_task:
                        main_class_name: com.cdo.{scala_pkg}.App
                      libraries:
                        - jar: ./target/scala-2.12/{dir_name}-assembly-0.1.0.jar
        """),
        )
        _write(
            root / "build.sbt",
            dedent(f"""
            name := "{dir_name}"
            version := "0.1.0"
            scalaVersion := "2.12.18"
            libraryDependencies += "org.apache.spark" %% "spark-sql" % "3.5.1" % "provided"
            libraryDependencies += "org.scalatest" %% "scalatest" % "3.2.18" % Test
        """),
        )
        _write(root / "project/build.properties", "sbt.version=1.10.1\n")
        _write(
            root / f"src/main/scala/com/cdo/{scala_pkg}/App.scala",
            dedent(f"""
            package com.cdo.{scala_pkg}
            object App {{
              def main(args: Array[String]): Unit = println("hello from {dir_name}")
            }}
        """),
        )


def scaffold_streaming(domain: str, name: str, kind: str) -> None:
    dir_name = f"streaming-{name}"
    pkg = dir_name.replace("-", "_")
    root = REPO_ROOT / "projects" / domain / dir_name
    print(f"Scaffolding streaming ({kind}): {root.relative_to(REPO_ROOT)}")

    _write(root / "AGENTS.md", _common_agents_md(dir_name, "streaming", domain))
    _write(
        root / "bundle.yml",
        dedent(f"""
        resources:
          jobs:
            {pkg}:
              name: {dir_name}-${{bundle.target}}
              tags: {{ bundle: {dir_name}, domain: {domain} }}
              continuous:
                pause_status: ${{if(bundle.target == "prod", "UNPAUSED", "PAUSED")}}
              tasks:
                - task_key: stream
                  notebook_task:
                    notebook_path: ./notebooks/stream.py
                    base_parameters: {{ catalog: ${{var.catalog}} }}
    """),
    )
    _write(
        root / "pyproject.toml",
        dedent(f"""
        [project]
        name = "{dir_name}"
        version = "0.1.0"
        requires-python = ">=3.11"
        dependencies = ["pyspark>=3.5"]

        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [tool.hatch.build.targets.wheel]
        packages = ["src/{pkg}"]
    """),
    )
    _write(root / f"src/{pkg}/__init__.py", "")
    _write(
        root / f"src/{pkg}/stream.py",
        dedent('''
        """Structured Streaming entry point."""

        def run(catalog: str) -> None:
            """TODO: implement streaming logic."""
            pass
    '''),
    )
    _write(root / "tests/test_stream.py", "def test_smoke(): pass\n")
    _write(
        root / "notebooks/stream.py",
        dedent(f"""
        # Databricks notebook source
        dbutils.widgets.text("catalog", "cdo_dev")
        catalog = dbutils.widgets.get("catalog")
        from {pkg}.stream import run
        run(catalog)
    """),
    )


def scaffold_app(domain: str, name: str, kind: str) -> None:
    dir_name = f"app-{name}"
    pkg = dir_name.replace("-", "_")
    root = REPO_ROOT / "projects" / domain / dir_name
    print(f"Scaffolding app: {root.relative_to(REPO_ROOT)}")

    _write(root / "AGENTS.md", _common_agents_md(dir_name, "app", domain))
    _write(
        root / "bundle.yml",
        dedent(f"""
        resources:
          apps:
            {pkg}:
              name: "{dir_name}-${{bundle.target}}"
              description: "TODO: describe this app"
              source_code_path: ./app
              config:
                command: ["streamlit", "run", "app.py"]
                env:
                  - name: CATALOG
                    value: ${{var.catalog}}
    """),
    )
    _write(
        root / "pyproject.toml",
        dedent(f"""
        [project]
        name = "{dir_name}"
        version = "0.1.0"
        requires-python = ">=3.11"
        dependencies = ["streamlit>=1.30"]

        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [tool.hatch.build.targets.wheel]
        packages = ["src/{pkg}"]
    """),
    )
    _write(
        root / "app/app.yaml",
        dedent("""
        command:
          - streamlit
          - run
          - app.py
        env:
          - name: CATALOG
            value: cdo_dev
    """),
    )
    _write(
        root / "app/app.py",
        dedent(f"""
        import os
        import streamlit as st
        from {pkg}.logic import load_data

        catalog = os.environ.get("CATALOG", "cdo_dev")
        df = load_data(catalog=catalog)
        st.dataframe(df)
    """),
    )
    _write(root / f"src/{pkg}/__init__.py", "")
    _write(
        root / f"src/{pkg}/logic.py",
        dedent('''
        """Business logic — unit-testable."""

        def load_data(catalog: str) -> list[dict]:
            """TODO: implement."""
            return [{"status": "ok", "catalog": catalog}]
    '''),
    )
    _write(
        root / "tests/test_logic.py",
        dedent(f"""
        from {pkg}.logic import load_data

        def test_load_data_returns_list() -> None:
            result = load_data("cdo_dev")
            assert isinstance(result, list)
            assert len(result) > 0
    """),
    )


def scaffold_dashboard(domain: str, name: str, kind: str) -> None:
    dir_name = f"dashboard-{name}"
    root = REPO_ROOT / "projects" / domain / dir_name
    print(f"Scaffolding dashboard: {root.relative_to(REPO_ROOT)}")

    _write(root / "AGENTS.md", _common_agents_md(dir_name, "dashboard", domain))
    _write(
        root / "bundle.yml",
        dedent(f"""
        resources:
          dashboards:
            {dir_name.replace("-", "_")}:
              display_name: "{name}"
              warehouse_id: ${{var.sql_warehouse_id}}
              file_path: ./dashboard.lvdash.json
    """),
    )
    _write(root / "dashboard.lvdash.json", '{"pages": []}\n')


def scaffold_api(domain: str, name: str, kind: str) -> None:
    dir_name = f"api-{name}"
    pkg = dir_name.replace("-", "_")
    root = REPO_ROOT / "projects" / domain / dir_name
    print(f"Scaffolding api: {root.relative_to(REPO_ROOT)}")

    _write(root / "AGENTS.md", _common_agents_md(dir_name, "api", domain))
    _write(
        root / "bundle.yml",
        dedent(f"""
        resources:
          apps:
            {pkg}:
              name: "{dir_name}-${{bundle.target}}"
              description: "TODO: describe this API"
              source_code_path: ./app
              config:
                command: ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
                env:
                  - name: CATALOG
                    value: ${{var.catalog}}
    """),
    )
    _write(
        root / "pyproject.toml",
        dedent(f"""
        [project]
        name = "{dir_name}"
        version = "0.1.0"
        requires-python = ">=3.11"
        dependencies = ["fastapi>=0.100", "uvicorn>=0.20"]

        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [tool.hatch.build.targets.wheel]
        packages = ["src/{pkg}"]
    """),
    )
    _write(
        root / "app/app.yaml",
        dedent("""
        command:
          - uvicorn
          - app:app
          - --host
          - "0.0.0.0"
          - --port
          - "8000"
        env:
          - name: CATALOG
            value: cdo_dev
    """),
    )
    _write(
        root / "app/app.py",
        dedent(f"""
        from fastapi import FastAPI
        from {pkg}.routes import router

        app = FastAPI(title="{dir_name}")
        app.include_router(router)
    """),
    )
    _write(root / f"src/{pkg}/__init__.py", "")
    _write(
        root / f"src/{pkg}/routes.py",
        dedent('''
        """API routes."""
        from fastapi import APIRouter

        router = APIRouter()

        @router.get("/health")
        def health() -> dict:
            return {"status": "ok"}
    '''),
    )
    _write(
        root / "tests/test_routes.py",
        dedent(f"""
        from {pkg}.routes import router

        def test_health_route_exists() -> None:
            routes = [r.path for r in router.routes]
            assert "/health" in routes
    """),
    )


def scaffold_sync(domain: str, name: str, kind: str) -> None:
    dir_name = f"sync-{name}"
    root = REPO_ROOT / "projects" / domain / dir_name
    print(f"Scaffolding sync: {root.relative_to(REPO_ROOT)}")

    _write(root / "AGENTS.md", _common_agents_md(dir_name, "sync", domain))
    _write(
        root / "bundle.yml",
        dedent(f"""
        resources:
          synced_database_tables:
            {dir_name.replace("-", "_")}:
              name: "{dir_name}"
              catalog_name: ${{var.catalog}}
              schema_name: TODO_schema
              table_name: TODO_table
    """),
    )
    _write(
        root / "lakebase/schema.sql",
        dedent("""
        -- Lakebase schema DDL (Postgres-compatible)
        -- TODO: define tables/views synced from Delta Lake
    """),
    )
    _write(
        root / "lakebase/views.sql",
        dedent("""
        -- Masked views for PII columns
        -- TODO: define views with appropriate masking
    """),
    )


def scaffold_capture(domain: str, name: str, kind: str) -> None:
    dir_name = f"capture-{name}"
    pkg = dir_name.replace("-", "_")
    root = REPO_ROOT / "projects" / domain / dir_name
    print(f"Scaffolding capture ({kind}): {root.relative_to(REPO_ROOT)}")

    _write(root / "AGENTS.md", _common_agents_md(dir_name, "capture", domain))
    _write(
        root / "bundle.yml",
        dedent(f"""
        resources:
          jobs:
            {pkg}:
              name: {dir_name}-${{bundle.target}}
              tags: {{ bundle: {dir_name}, domain: {domain} }}
              tasks:
                - task_key: capture
                  notebook_task:
                    notebook_path: ./notebooks/capture.py
                    base_parameters: {{ catalog: ${{var.catalog}} }}
    """),
    )
    _write(
        root / "pyproject.toml",
        dedent(f"""
        [project]
        name = "{dir_name}"
        version = "0.1.0"
        requires-python = ">=3.11"
        dependencies = ["pyspark>=3.5"]

        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [tool.hatch.build.targets.wheel]
        packages = ["src/{pkg}"]
    """),
    )
    _write(root / f"src/{pkg}/__init__.py", "")
    _write(
        root / f"src/{pkg}/capture.py",
        dedent('''
        """CDC / operational capture logic."""

        def run(catalog: str) -> None:
            """TODO: implement capture logic."""
            pass
    '''),
    )
    _write(root / "tests/test_capture.py", "def test_smoke(): pass\n")
    _write(
        root / "notebooks/capture.py",
        dedent(f"""
        # Databricks notebook source
        dbutils.widgets.text("catalog", "cdo_dev")
        catalog = dbutils.widgets.get("catalog")
        from {pkg}.capture import run
        run(catalog)
    """),
    )


FUNCTION_SCAFFOLDERS = {
    "pipeline": scaffold_pipeline,
    "streaming": scaffold_streaming,
    "app": scaffold_app,
    "dashboard": scaffold_dashboard,
    "api": scaffold_api,
    "sync": scaffold_sync,
    "capture": scaffold_capture,
}


def scaffold_lib(name: str) -> None:
    pkg = name.replace("-", "_")
    root = REPO_ROOT / "libs" / pkg
    print(f"Scaffolding lib: {root.relative_to(REPO_ROOT)}")

    # Package root IS the importable module (flat layout, no src/ wrapper)
    _write(root / "__init__.py", f'"""{pkg} — shared lib."""\n')

    _write(
        root / "pyproject.toml",
        dedent(f"""
        [project]
        name = "{name}"
        version = "0.1.0"
        description = "TODO: one-line description"
        requires-python = ">=3.11"
        dependencies = []

        [project.optional-dependencies]
        dev = [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "ruff>=0.4",
        ]

        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [tool.hatch.build.targets.wheel]
        packages = ["."]

        [tool.ruff]
        line-length = 100
        target-version = "py311"

        [tool.pytest.ini_options]
        testpaths = ["tests"]
    """),
    )

    _write(
        root / "AGENTS.md",
        dedent(f"""\
        # {pkg}

        TODO: one paragraph describing what this library provides.

        **Location**: `libs/{pkg}/`
        **Import path**: `from {pkg}.<module> import <function>`
        **Notebook setup**: `sys.path.append("/Workspace/Repos/shared/mono-dev/libs")`

        ## Owner
        @cdo/<team>

        ## When to use what

        | I need to... | Import | Required args |
        |---|---|---|
        | TODO | `from {pkg}.<module> import <function>` | `spark, ...` |

        ## Folder structure (for agents)

        ```
        libs/{pkg}/
        ├── __init__.py           <- Public API re-exports
        ├── AGENTS.md             <- You are here
        ├── pyproject.toml        <- Package metadata
        ├── (your modules here)
        └── tests/
        ```

        ## Rules
        - Pass `spark` explicitly as first arg (per ADR-0002)
        - Pure functions must NOT accept `spark`
        - All table paths fully qualified: `catalog.schema.table`

        ## Local dev

        ```bash
        make test P=libs/{pkg}
        make lint P=libs/{pkg}
        ```
    """),
    )

    _write(root / "tests/__init__.py", "")
    _write(
        root / "tests/test_smoke.py",
        dedent(f"""\
        import pytest


        @pytest.mark.unit
        def test_import():
            import {pkg}
            assert {pkg} is not None
    """),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold new projects and libs.")
    sub = parser.add_subparsers(dest="command", required=True)

    proj = sub.add_parser("project", help="Create a new project")
    proj.add_argument("--domain", required=True, help="Business domain (e.g. finance, hcm, infra)")
    proj.add_argument(
        "--function",
        required=True,
        choices=VALID_FUNCTIONS,
        help=f"Project function type: {', '.join(VALID_FUNCTIONS)}",
    )
    proj.add_argument("--name", required=True, help="Subdomain name (e.g. accounts-payable)")
    proj.add_argument("--kind", choices=["python", "scala"], default="python", help="Language")

    lib_parser = sub.add_parser("lib", help="Create a new shared library")
    lib_parser.add_argument("--name", required=True)

    args = parser.parse_args()

    if args.command == "project":
        domain = args.domain.lower()
        scaffolder = FUNCTION_SCAFFOLDERS[args.function]
        scaffolder(domain, args.name, args.kind)
        dir_name = f"{args.function}-{args.name}"
        print(f"\nDone. Created: projects/{domain}/{dir_name}/")
        print(
            f"Remember to add 'projects/{domain}/{dir_name}' to pyproject.toml [tool.uv.workspace] members."
        )
    elif args.command == "lib":
        scaffold_lib(args.name)
        pkg = args.name.replace("-", "_")
        print(f"\nDone. Created: libs/{pkg}/")
        print("\nNext steps:")
        print(f"  1. Add 'libs/{pkg}' to root pyproject.toml [tool.uv.workspace] members")
        print(f"  2. Fill in libs/{pkg}/AGENTS.md with lookup tables")
        print("  3. Update libs/AGENTS.md available libraries table")
        print("  4. Update libs/README.md available libraries table")

    return 0


if __name__ == "__main__":
    sys.exit(main())
