# terraform-databricks/

The single source of truth for what exists in our Databricks workspace.

Files:
- `main.tf` — provider config + workspace.
- `catalogs.tf` — Unity Catalog catalogs (per environment).
- `groups.tf` — workspace groups (synced from GitLab SCIM).
- `sps.tf` — service principals and their grants.
- `variables.tf` — environment-specific inputs.

See `infra/README.md` for the change-management flow.
