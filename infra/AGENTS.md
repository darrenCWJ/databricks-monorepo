# infra/ — Infrastructure as Code

## What goes here
Terraform modules for Databricks workspace provisioning and Unity Catalog
configuration. Touch with care — changes here affect all environments.

## Structure
```
infra/
├── modules/           # Terraform child modules (iam, compute, unity_catalog, grants, storage, workspace)
├── main.tf            # Root module wiring child modules together
├── variables.tf       # Input variables
└── environments/      # Per-env tfvars (dev/staging/prod)
```

## Related docs
- `docs/walkthrough.md` — infra walkthrough
- `docs/adr/0005-workspace-module-design.md` — workspace module architecture decision

## Rules
1. All access grants must be declarative (in Terraform), never manual UI clicks.
2. Changes require `@cdo/platform-team` + `@cdo/data-governance` review.
3. Unity Catalog changes also require `@cdo/security` review.
4. Never hardcode service principal IDs — use variables per environment.
5. Test with `terraform plan` before applying.

## Ownership
Platform team owns all infra. Data governance co-owns Unity Catalog.
