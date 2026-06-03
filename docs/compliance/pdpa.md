# Singapore PDPA controls

The Singapore Personal Data Protection Act (PDPA) requires consent, purpose
limitation, access, correction, transfer, and erasure. The relevant
implementation pieces in this repo:

| PDPA obligation | Implementation here |
|---|---|
| Purpose limitation | Column-level `meta.pii` and `meta.purpose` tags on every dbt model |
| Access (DSAR) | `apps/pdpa-dsar/` (skeleton; build in Wave 2 of migration) |
| Erasure (right to be forgotten) | `apps/pdpa-erasure/` — service-principal job, ticket-gated, audit-logged |
| Data residency (Singapore) | All Databricks workspaces in `ap-southeast-1`; UC storage in same region; cross-region writes blocked |
| Audit trail | `cdo_${env}.audit.pdpa_erasures` Delta table; deploy records in S3 with Object Lock |
| Notification of breach | Out-of-scope for this repo (security/legal) |

## Region pinning

Single region: `ap-southeast-1`. The `region` variable in `databricks.yml`
makes this explicit. Pre-commit check `tools/scripts/check_residency.py`
(TODO) scans for cross-region S3 paths in code and blocks.

## Erasure SLA

PDPA does not specify a fixed deadline (unlike GDPR's 30 days) but our
internal SLA is **15 business days from ticket open to confirmed erasure**.
The `apps/pdpa-erasure/` job runs in a single working day; the remaining
budget covers Legal review and ticketing.
