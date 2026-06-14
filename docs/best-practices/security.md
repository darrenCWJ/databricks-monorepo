# Security

> This doc is about **how we work**. The compliance mappings (which control
> maps to which behaviour) live in `docs/compliance/`.

## Classification — every column, every contract

The four-tier model:

| Tier | Examples | Storage |
|---|---|---|
| **Official-Open** | Public schedules, published policies | Any catalog |
| **Official-Closed** | Internal financial KPIs | Default catalog |
| **Restricted** | Personally identifying information (PII), supplier financials | Catalog with column masks |
| **Confidential** | Cleared-personnel records | Catalog firewalled to cleared groups only |

Every column in a Delta write contract MUST declare:

```yaml
columns:
  - name: nric
    classification: Restricted
    pii: true
    mask_function: cdo_core.mask_nric
    sensitivity: 4
    retention_days: 90
```

Pre-commit blocks the MR if any of `classification`, `pii`,
`sensitivity`, `retention_days` is missing on a Restricted column.

## Least privilege

- **Engineers have read-only access to prod catalogs by default.**
- **Write access is granted per-job to the service principal**, not to
  a user.
- **Service principals are scoped to one app.** No "shared" SP across
  multiple apps.
- **Cleared groups** (for Confidential data) are managed in GitLab,
  SCIM-synced to Databricks groups, and granted at the catalog level.

## PII handling

- **Mask at read time, not at write time.** The raw value lives in the
  table; column masks return null / hashed value to unauthorised
  readers. This lets PDPA erasure work without rewriting the lake.
- **Mask functions live in `libs/common-masks/`** — never duplicated
  per project.
- **Hashing is salted, with the salt in a secret scope** — not in code,
  not in the table.

## Secrets

See `secrets-and-config.md`. Short version: secret scopes only, rotation
every 90 days, no `.env` files anywhere.

## Audit trail

- **Every deploy is logged** to a WORM S3 bucket via
  `tools/scripts/audit_log.py`.
- **Every MR merge has a change-ticket ID** (Jira) — SOC2 requires the
  change record.
- **Every access grant** flows through Terraform — never a console click.

## What to do when you find a secret in a commit

1. Stop. Don't push if you haven't already.
2. Rotate the secret in the source system immediately.
3. Rewrite history if it's not yet pushed: `git reset HEAD~1`.
4. If already pushed: tell @cdo/security in #incidents.
   The MR is paused, secret is rotated, history is rewritten via
   `git filter-repo`, force-pushed by platform team.

## What to do when an external party reports a vulnerability

1. Open a P1 incident in PagerDuty.
2. Coordinate response in #incidents.
3. Public disclosure timeline is set by @cdo/security, not by the team.
