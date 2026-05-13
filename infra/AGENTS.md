# infra/ — Infrastructure as Code

## What goes here
Terraform modules for Databricks workspace provisioning and Unity Catalog
configuration. Touch with care — changes here affect all environments.

## Structure
```
infra/
├── terraform-databricks/   # Workspace-level resources (clusters, pools, instance profiles)
└── unity-catalog/          # Catalogs, schemas, grants, column masks, row filters
```

## Rules
1. All access grants must be declarative (in Terraform), never manual UI clicks.
2. Changes require `@cdo/platform-team` + `@cdo/data-governance` review.
3. Unity Catalog changes also require `@cdo/security` review.
4. Never hardcode service principal IDs — use variables per environment.
5. Test with `terraform plan` before applying.

## Ownership
Platform team owns all infra. Data governance co-owns Unity Catalog.
