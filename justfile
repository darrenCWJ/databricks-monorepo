# justfile — canonical command surface
# Install just: https://github.com/casey/just

set shell := ["bash", "-uc"]
set positional-arguments

# default: list available commands
default:
    @just --list

# ----- bootstrap -----
setup:
    uv sync --all-packages
    uv run pre-commit install
    @echo "(sbt update will run on first scala build)"

# ----- tests -----
test PATH=".":
    uv run pytest {{PATH}} -x

test-cov PATH=".":
    uv run pytest {{PATH}} --cov --cov-report=term-missing

# ----- linting -----
lint PATH=".":
    uv run ruff check {{PATH}}
    uv run ruff format --check {{PATH}}
    -uv run mypy {{PATH}}

fix PATH=".":
    uv run ruff check --fix {{PATH}}
    uv run ruff format {{PATH}}

# ----- Databricks Asset Bundles -----
bundle-validate PATH:
    cd {{PATH}} && databricks bundle validate

bundle-deploy PATH TARGET="dev":
    cd {{PATH}} && databricks bundle deploy -t {{TARGET}}

bundle-destroy PATH TARGET="dev":
    cd {{PATH}} && databricks bundle destroy -t {{TARGET}} --auto-approve

bundle-run PATH JOB TARGET="dev":
    cd {{PATH}} && databricks bundle run -t {{TARGET}} {{JOB}}

# ----- Scala / sbt -----
sbt-test PATH:
    cd {{PATH}} && sbt test

sbt-assembly PATH:
    cd {{PATH}} && sbt assembly

# ----- scaffolding -----
new-app NAME KIND="python":
    uv run python tools/scripts/scaffold.py app --name {{NAME}} --kind {{KIND}}

new-lib NAME:
    uv run python tools/scripts/scaffold.py lib --name {{NAME}}


# Import an existing Databricks Job into a target app directory.
# Run `just new-app NAME --kind python` first to create the target.
# See docs/runbooks/import-existing-job.md for the full lifecycle.
import-job JOB_ID TARGET:
    uv run python tools/scripts/import_job.py {{JOB_ID}} {{TARGET}}


# Find where a resource is defined and what depends on it.
where-is MODEL:
    uv run python tools/scripts/where_is.py {{MODEL}}

# ----- change-impact -----
affected:
    uv run python tools/scripts/affected.py

# ----- migration helpers -----
diff-outputs BUNDLE LEGACY:
    uv run python tools/scripts/diff_outputs.py --bundle {{BUNDLE}} --legacy {{LEGACY}}

# ----- everything CI runs -----
ci-local:
    just lint
    just test
    @for bundle in $(find apps -maxdepth 2 -name bundle.yml -exec dirname {} \;); do \
      echo ">>> validating $bundle"; \
      just bundle-validate $bundle; \
    done

# ----- compliance / SOC2 -----
dump-access TARGET="prod":
    uv run python tools/scripts/dump_access.py --target {{TARGET}}

audit-log BUNDLE TARGET SHA:
    uv run python tools/scripts/audit_log.py --bundle {{BUNDLE}} --target {{TARGET}} --sha {{SHA}}
