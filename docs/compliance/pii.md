# PII handling

Every column in every dbt model and every Delta table is classified
explicitly. The classification is enforced by pre-commit, surfaced in
Unity Catalog tags, and used by the masking function.

## Workflow

1. Engineer adds a column to a dbt model. Schema yaml must include:
   ```yaml
   - name: email
     data_type: string
     meta: { pii: true, pii_class: contact, purpose: contact_user }
   ```
2. Pre-commit hook `check_pii_contract.py` blocks the MR if `meta.pii` is
   absent.
3. dbt run applies a Unity Catalog tag `pii=true` to the column (via a
   post-hook macro; TODO add).
4. The `mask_pii` UC function (Terraform-managed) intercepts SELECTs on
   pii-tagged columns and returns 'REDACTED' unless the caller is in the
   `cdo_pii_readers_${env}` group.

## CODEOWNERS routing

Any MR that adds or modifies a column with `pii: true` is auto-routed to
`@cdo/data-governance` for review (via CODEOWNERS rule on `docs/compliance/`
plus a custom GitLab merge-request rule on schema.yml diffs).

## What the agent can and cannot do

Agents can add columns and propose `meta.pii: true|false`. The data-governance
human reviewer must confirm before merge — explicit gate; agent does not
self-classify.
