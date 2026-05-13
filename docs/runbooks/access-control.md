# Runbook: access control (four layers, all declarative)

Every grant in this platform lives in a version-controlled file, goes through
CODEOWNERS review, and shows up in the quarterly audit dump. No "click in the
Databricks UI to grant access" — that path is closed.

This runbook covers each of the four layers, how to add an entitlement, how
to verify it took effect, and how to roll back.

## The four layers

| Layer | What it gates | Where it lives | Approver |
|---|---|---|---|
| L1  Workspace | Who can sign in; which SP a Job runs as | GitLab group -> SCIM sync; `apps/*/bundle.yml` `run_as:` | HR/Identity (humans); `@cdo/platform-team` (SPs) |
| L2  Grants | USE_CATALOG, SELECT, MODIFY, CREATE on UC objects | `infra/unity-catalog/main.tf` `databricks_grant` resources | `@cdo/platform-team` + `@cdo/data-governance` |
| L3  Column masks | Per-column visibility (clear vs REDACTED) | `dbt/*/schema.yml` `meta.mask_function` + `infra/unity-catalog/main.tf` function defs + `dbt/*/macros/apply_masks.sql` | `@cdo/data-governance` + `@cdo/restricted-cleared` |
| L4  Row filters | Which rows a caller can see | `dbt/*/schema.yml` `config.row_filter` + `infra/unity-catalog/main.tf` filter functions + `dbt/*/macros/apply_row_filter.sql` | `@cdo/data-governance` + `@cdo/restricted-cleared` |

## Layer 1 — workspace access

### Adding a human user

```bash
glab api -X POST "groups/cdo%2Ffinance-team/members" \
  -F user_id=$(glab api users?username=newjoiner.lim | jq '.[0].id') \
  -F access_level=30
```

That's it — no repo edit. The Databricks workspace is provisioned via SCIM
sync from GitLab; the user appears within minutes.

### Adding a service principal

```hcl
# infra/unity-catalog/main.tf
resource "databricks_service_principal" "finance_pipelines" {
  display_name = "cdo_finance_pipelines_${var.environment}"
}
```

Open MR. `@cdo/platform-team` reviews. CI plans + applies on merge.

In `apps/finance-*/bundle.yml`, reference the SP:

```yaml
targets:
  staging:
    run_as:
      service_principal_name: cdo_finance_pipelines_staging
```

## Layer 2 — catalog/schema/table grants

Pattern: humans get SELECT, service principals get MODIFY.

```hcl
resource "databricks_grants" "finance_silver_grants" {
  schema = "${databricks_catalog.main.name}.silver"

  grant {
    principal  = "cdo_finance_team_${var.environment}"
    privileges = ["SELECT"]
  }
  grant {
    principal  = databricks_service_principal.finance_pipelines.application_id
    privileges = ["SELECT", "MODIFY", "CREATE_TABLE"]
  }
}
```

### Verifying

```bash
databricks unity-catalog grants get cdo_${env}.silver
```

### Removing

Delete the resource block. Terraform apply revokes the grant. Audit-log
captures the timestamp + actor.

## Layer 3 — column masks (PII gate)

### Declare in schema.yml

```yaml
models:
  - name: fct_customers
    columns:
      - name: email
        data_type: string
        meta:
          pii: true
          classification: Restricted
          sensitivity: Sensitive-High
          retention_days: 2555
          mask_function: security.mask_pii
```

Pre-commit hook `check_pii_contract.py` blocks the MR if a Restricted column
is missing `meta.mask_function`. The author either:
- Declares the function name (most common), or
- Sets `meta.no_mask_required: true` with a comment explaining why (needs
  `@cdo/data-governance` review).

### Define the function (Terraform)

```hcl
resource "databricks_function" "mask_pii" {
  name               = "cdo_${var.environment}.security.mask_pii"
  catalog_name       = "cdo_${var.environment}"
  schema_name        = "security"
  input_params       = jsonencode([{ name = "value", type_text = "STRING" }])
  return_params      = jsonencode({ type_text = "STRING" })
  routine_definition = <<-SQL
    CASE
      WHEN is_account_group_member('cdo_pii_readers_${var.environment}') THEN value
      ELSE 'REDACTED'
    END
  SQL
}
```

### Apply via dbt post-hook

```sql
-- dbt/platform-core/macros/apply_masks.sql
{% macro apply_masks() %}
  {% for col in graph.nodes[model.unique_id].columns.values() %}
    {% if col.meta.mask_function %}
      ALTER TABLE {{ this }}
      ALTER COLUMN {{ col.name }}
      SET MASK {{ col.meta.mask_function }};
    {% endif %}
  {% endfor %}
{% endmacro %}
```

Reference it in `dbt_project.yml`:

```yaml
models:
  platform_core:
    +post-hook: "{{ apply_masks() }}"
```

### Verifying

```sql
SHOW MASKS ON cdo_${env}.silver.fct_customers;
-- Expect: email -> security.mask_pii
```

Or query directly as different users:

```sql
-- As @cdo/finance-team (no pii_readers membership):
SELECT email FROM cdo_dev.silver.fct_customers LIMIT 1;
-- email
-- REDACTED

-- As @cdo/data-governance (member of cdo_pii_readers_dev):
-- email
-- jane@example.com
```

## Layer 4 — row-level filters

### Declare in schema.yml

```yaml
models:
  - name: fct_budget_variance
    config:
      contract: { enforced: true }
      row_filter:
        function: security.filter_by_cost_centre
        on_columns: [cost_centre]
    columns:
      - name: cost_centre
        meta: { pii: false, classification: Restricted, sensitivity: Sensitive-High,
                retention_days: 2555, mask_function: security.mask_pii }
      # ...
```

### Define the filter function (Terraform)

```hcl
resource "databricks_function" "filter_by_cost_centre" {
  name               = "cdo_${var.environment}.security.filter_by_cost_centre"
  catalog_name       = "cdo_${var.environment}"
  schema_name        = "security"
  input_params       = jsonencode([{ name = "cost_centre", type_text = "STRING" }])
  return_params      = jsonencode({ type_text = "BOOLEAN" })
  routine_definition = <<-SQL
    CASE
      WHEN is_account_group_member('cdo_pii_readers_${var.environment}') THEN TRUE
      WHEN is_account_group_member('cdo_finance_team_${var.environment}') THEN
        cost_centre IN (
          SELECT cost_centre
          FROM cdo_${var.environment}.security.finance_user_scope
          WHERE user_email = current_user()
        )
      ELSE FALSE
    END
  SQL
}
```

### Apply via dbt post-hook

```sql
-- dbt/platform-core/macros/apply_row_filter.sql
{% macro apply_row_filter() %}
  {% set rf = config.get('row_filter') %}
  {% if rf %}
    ALTER TABLE {{ this }}
      SET ROW FILTER {{ rf.function }}
      ON ({{ rf.on_columns | join(', ') }});
  {% endif %}
{% endmacro %}
```

### Verifying

```sql
SHOW ROW FILTERS ON cdo_${env}.silver.fct_budget_variance;
-- Expect: security.filter_by_cost_centre ON (cost_centre)
```

Query as different users; each sees a different row set.

### Adding a new user to the scope table

```diff
# infra/unity-catalog/seeds/finance_user_scope.csv
 user_email,cost_centre
 alice.tan@cdo.gov.sg,FINANCE
+jane.lim@cdo.gov.sg,HR
 ...
```

Open MR. `@cdo/finance-team` + `@cdo/data-governance` approve. Apply.
Jane now sees HR-cost-centre rows in every row-filtered table.

## Lakebase mirror

For tables synced to Lakebase, mirror the masking/filtering at the Postgres
layer in `apps/<name>/lakebase/views.sql`:

```sql
-- Masked view; app service reads this, not the underlying table.
CREATE VIEW customer_data.customer_360_masked AS
SELECT
  customer_id,
  CASE WHEN current_user IN (SELECT user FROM pii_readers)
       THEN email ELSE 'REDACTED' END AS email,
  segment,
  lifetime_value
FROM customer_data.customer_360;

-- Row-level: PostgreSQL RLS
ALTER TABLE customer_data.customer_360 ENABLE ROW LEVEL SECURITY;
CREATE POLICY customer_segment_policy ON customer_data.customer_360
  FOR SELECT
  USING (current_user IN (SELECT user FROM customer_full_access)
         OR segment = current_setting('app.user_segment', true));
```

Same governance principle, applied at sync target. The pre-commit hook
(when extended for Lakebase) will verify every PII column in a synced
table has either a masked view OR an explicit `no_lakebase_mask` flag.

## A worked example end-to-end

Question: A Finance analyst writes `SELECT * FROM cdo_prod.gold.fct_budget_variance`. What happens?

```
1. Query hits Unity Catalog
2. UC checks Layer 2: analyst (via @cdo/finance-team) has SELECT on cdo_prod.gold. Yes.
3. UC checks Layer 4: table has ROW FILTER filter_by_cost_centre.
   Function evaluates per row using current_user().
   Analyst is in finance_team -> sees only their entitled cost_centre rows.
4. UC checks Layer 3: for each column, apply mask if declared.
   cost_centre, budget_amount, period: no mask -> clear.
   cost_centre_owner_email: mask_pii -> REDACTED unless in pii_readers.
5. Result returned: filtered rows, masked PII columns.
```

One query, four layers of gating, all declared in version-controlled files.

## Quarterly audit

```bash
just dump-access prod
```

Produces under `reviews/YYYY-MM-DD/`:

- `codeowners.csv` — Layer 1
- `databricks_workspace_acls.csv` — Layer 1
- `uc_grants.csv` — Layer 2
- `uc_column_masks.csv` — Layer 3
- `uc_row_filters.csv` — Layer 4
- `lakebase_grants.csv` — mirror

`@cdo/data-governance` walks each. Stale entries removed via MR. The folder
is committed to the repo as audit evidence (intentionally NOT gitignored).

## See also

- `docs/compliance/pii.md` — what we classify as PII and why
- `docs/compliance/im8.md` — IM8 Tier 1 control map
- `docs/runbooks/codeowners-maintenance.md` — when L1 group membership changes
- `docs/runbooks/lakebase-sync-design.md` — mirroring grants to Postgres
