# Data Governance Rules

## Column Classification (mandatory on every Delta write)

Every column in a dbt model or Delta table must declare:
- `pii: true|false`
- `classification: Official|Restricted`
- `sensitivity: Non-Sensitive|Sensitive-Normal|Sensitive-High`
- `retention_days: <integer>`

Pre-commit hook `check_pii_contract.py` blocks MRs missing these.

## Column Masks

- Every `Restricted` column MUST have `meta.mask_function` declared.
- If no mask needed, set `meta.no_mask_required: true` with justification.
- Mask functions live in `infra/unity-catalog/main.tf`.
- Applied via dbt post-hook `apply_masks()`.

## Row Filters

- Declared in `schema.yml` under `config.row_filter`.
- Filter functions in `infra/unity-catalog/main.tf`.
- Applied via dbt post-hook `apply_row_filter()`.

## Access Grants

- All grants are declarative in Terraform. No manual UI clicks.
- Humans get SELECT; service principals get MODIFY.
- Changes require `@cdo/platform-team` + `@cdo/data-governance` review.

## Agent Behaviour

- REFUSE any task that writes Restricted data without verifying mask_function exists.
- REFUSE any task that adds a column without full classification metadata.
- Flag any cross-team data read that bypasses the contract layer.
