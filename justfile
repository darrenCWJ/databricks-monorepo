# Local task runner. `just --list` to see everything.

default:
    @just --list

setup:
    uv sync --all-extras
    uv run pre-commit install

lint scope="":
    uv run ruff check {{scope}}
    uv run ruff format --check {{scope}}

test scope="":
    uv run pytest {{scope}}

new-app name kind="python":
    python tools/scripts/scaffold.py app --name {{name}} --kind {{kind}}

new-lib name:
    python tools/scripts/scaffold.py lib --name {{name}}

migrate source name team mode="history":
    python tools/scripts/migrate_repo.py --source {{source}} --name {{name}} --team {{team}} --mode {{mode}}

where-is target:
    python tools/scripts/where_is.py {{target}}

affected:
    python tools/scripts/affected.py

bundle-validate scope="":
    databricks bundle validate {{scope}}

bundle-run app task target="dev":
    databricks bundle run {{app}}.{{task}} -t {{target}}
