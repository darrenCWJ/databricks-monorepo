# 0003: Create finance-payment-recon

## Status
Accepted

## Context
The finance team needs daily reconciliation of payment transactions against
bank statements to detect and flag discrepancies. Currently this is a manual
process. Automating it as a Databricks Asset Bundle gives the team a reliable,
auditable daily run with a gold-layer output they can query directly.

## Decision
Create `apps/finance-payment-recon` as a two-task Databricks Asset Bundle
owned by @cdo/finance-team:
- Task 1 (`api_ingest`): fetch from external payments API, land into `bronze.raw_payments`
- Task 2 (`reconcile`): compare against bank statements, write `gold.payment_recon`

## Consequences
- `gold.payment_recon` is a new output table — downstream consumers should be
  registered in AGENTS.md as they onboard
- The API client stub in `ingest.py` must be implemented before the first production deploy
- Discrepancy threshold (`0.01`) is contractual — changes require finance-team approval

## Owner
@cdo/finance-team
