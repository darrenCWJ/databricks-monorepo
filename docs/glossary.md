# Glossary

| Term | Meaning |
|---|---|
| **DAB** | Databricks Asset Bundle — a directory with `bundle.yml` describing jobs, resources, and per-target config. The unit of deployment. |
| **uv workspace** | A set of Python packages sharing one `uv.lock`. Members live under `apps/*` and `libs/*`. |
| **dbt mesh** | A pattern of splitting one giant dbt project into per-domain projects with explicit cross-project model references. |
| **affected scope** | The set of DABs, libs, or dbt projects that a PR's git diff impacts. Computed by `tools/scripts/affected.py`. |
| **shadow write** | During migration, the new code writes to a separate output location alongside legacy. Used for diff validation before cut-over. |
| **catalog** | Unity Catalog top-level namespace. We use `cdo_dev`, `cdo_staging`, `cdo_prod`. |
| **target** | A DAB deployment environment (`dev`, `staging`, `prod`). Defined in root `databricks.yml`. |
| **thin notebook** | A Databricks notebook that contains only widget wiring + a function call. All logic lives in `src/`. |
