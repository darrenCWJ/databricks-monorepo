# Makefile — canonical command surface
# GNU Make 3.81+ (pre-installed on macOS and Linux).
#
# Usage:
#   make <target>              — run with defaults
#   make <target> P=apps/foo   — override path variable
#
# Examples:
#   make test                  — run all tests (P defaults to ".")
#   make test P=apps/finance-payment-recon
#   make bundle-deploy P=apps/finance-payment-recon T=staging

SHELL := /bin/bash
.SHELLFLAGS := -euc
.DEFAULT_GOAL := help

# ----- default variables -----
P       ?= .
T       ?= dev
KIND    ?= python

# ----- help -----
.PHONY: help
help: ## Show available commands
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-22s %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables (pass as VAR=value):"
	@echo "  P       Target path (default: .)"
	@echo "  T       Deploy target (default: dev)"
	@echo "  KIND    App kind for scaffolding (default: python)"
	@echo "  NAME    Project name (required for new-app, new-lib)"
	@echo "  JOB     Job key (required for bundle-run)"
	@echo "  JOB_ID  Databricks job ID (required for import-job)"
	@echo "  MODEL   Model name (required for where-is)"
	@echo "  BUNDLE  Bundle path (required for diff-outputs, audit-log)"
	@echo "  LEGACY  Legacy path (required for diff-outputs)"
	@echo "  SHA     Git SHA (required for audit-log)"

# ----- bootstrap -----
.PHONY: setup
setup: ## Install all deps, set up pre-commit
	uv sync --all-packages
	uv run pre-commit install
	@echo "(sbt update will run on first scala build)"

# ----- tests -----
.PHONY: test
test: ## Run pytest (P=path, default .)
	uv run pytest $(P) -x

.PHONY: test-cov
test-cov: ## Run tests with coverage (P=path)
	uv run pytest $(P) --cov --cov-report=term-missing

# ----- linting -----
.PHONY: lint
lint: ## Lint: ruff + mypy (P=path)
	uv run ruff check $(P)
	uv run ruff format --check $(P)
	-uv run mypy $(P)

.PHONY: fix
fix: ## Auto-fix lint issues (P=path)
	uv run ruff check --fix $(P)
	uv run ruff format $(P)

# ----- Databricks Asset Bundles -----
.PHONY: bundle-validate
bundle-validate: ## Validate a DAB (P=path)
	cd $(P) && databricks bundle validate

.PHONY: bundle-deploy
bundle-deploy: ## Deploy a DAB (P=path, T=target)
	cd $(P) && databricks bundle deploy -t $(T)

.PHONY: bundle-destroy
bundle-destroy: ## Tear down a DAB (P=path, T=target)
	cd $(P) && databricks bundle destroy -t $(T) --auto-approve

.PHONY: bundle-run
bundle-run: ## Trigger a job run (P=path, JOB=key, T=target)
ifndef JOB
	$(error JOB is required. Usage: make bundle-run P=apps/foo JOB=task_key)
endif
	cd $(P) && databricks bundle run -t $(T) $(JOB)

# ----- Scala / sbt -----
.PHONY: sbt-test
sbt-test: ## Run sbt tests (P=path)
	cd $(P) && sbt test

.PHONY: sbt-assembly
sbt-assembly: ## Build fat JAR (P=path)
	cd $(P) && sbt assembly

# ----- scaffolding -----
.PHONY: list-libs
list-libs: ## Show available shared libraries and what they provide (KEYWORD=optional)
	uv run python tools/scripts/list_libs.py $(if $(KEYWORD),--keyword $(KEYWORD),)

.PHONY: new-app
new-app: ## Scaffold new app (NAME=name, KIND=python|scala)
ifndef NAME
	$(error NAME is required. Usage: make new-app NAME=finance-recon KIND=python)
endif
	@echo ""
	@echo "Available shared libraries (check before writing new code):"
	@echo "-------------------------------------------------------------"
	uv run python tools/scripts/list_libs.py
	@echo "-------------------------------------------------------------"
	@echo "Proceeding with scaffold for: $(NAME)"
	@echo ""
	uv run python tools/scripts/scaffold.py app --name $(NAME) --kind $(KIND)
	$(MAKE) data-map

.PHONY: new-lib
new-lib: ## Scaffold new shared library (NAME=name)
ifndef NAME
	$(error NAME is required. Usage: make new-lib NAME=finance-common)
endif
	uv run python tools/scripts/scaffold.py lib --name $(NAME)

# ----- import -----
.PHONY: import-job
import-job: ## Import existing Databricks Job (JOB_ID=id, T=target_path)
ifndef JOB_ID
	$(error JOB_ID is required. Usage: make import-job JOB_ID=123 T=apps/foo)
endif
	uv run python tools/scripts/import_job.py $(JOB_ID) $(T)

# ----- discovery -----
.PHONY: where-is
where-is: ## Locate a model and its consumers (MODEL=name)
ifndef MODEL
	$(error MODEL is required. Usage: make where-is MODEL=fct_orders)
endif
	uv run python tools/scripts/where_is.py $(MODEL)

# ----- change-impact -----
.PHONY: affected
affected: ## List bundles affected by current git diff
	uv run python tools/scripts/affected.py

# ----- data map -----
.PHONY: data-map
data-map: ## Regenerate docs/data-architecture.md from AGENTS.md files
	uv run python tools/scripts/gen_data_map.py

.PHONY: check-data-map
check-data-map: ## Verify data-architecture.md is up to date (CI)
	uv run python tools/scripts/gen_data_map.py --check

.PHONY: platform-health
platform-health: ## Cross-reference CODEOWNERS, data-architecture.md, and disk (manager report)
	uv run python tools/scripts/check_platform_health.py

# ----- migration helpers -----
.PHONY: diff-outputs
diff-outputs: ## Compare bundle vs legacy output (BUNDLE=path, LEGACY=path)
ifndef BUNDLE
	$(error BUNDLE is required. Usage: make diff-outputs BUNDLE=apps/foo LEGACY=/old)
endif
ifndef LEGACY
	$(error LEGACY is required. Usage: make diff-outputs BUNDLE=apps/foo LEGACY=/old)
endif
	uv run python tools/scripts/diff_outputs.py --bundle $(BUNDLE) --legacy $(LEGACY)

# ----- everything CI runs -----
.PHONY: ci-local
ci-local: ## Run full CI locally
	$(MAKE) lint
	$(MAKE) test
	@for bundle in $$(find apps -maxdepth 2 -name bundle.yml -exec dirname {} \;); do \
	  echo ">>> validating $$bundle"; \
	  $(MAKE) bundle-validate P=$$bundle; \
	done

# ----- compliance / SOC2 -----
.PHONY: dump-access
dump-access: ## Export access grants for audit (T=target, default prod)
	uv run python tools/scripts/dump_access.py --target $(T)

.PHONY: audit-log
audit-log: ## Record deploy audit entry (BUNDLE, T=target, SHA)
ifndef BUNDLE
	$(error BUNDLE is required. Usage: make audit-log BUNDLE=apps/foo T=prod SHA=abc123)
endif
ifndef SHA
	$(error SHA is required. Usage: make audit-log BUNDLE=apps/foo T=prod SHA=abc123)
endif
	uv run python tools/scripts/audit_log.py --bundle $(BUNDLE) --target $(T) --sha $(SHA)
