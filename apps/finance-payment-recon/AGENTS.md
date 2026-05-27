# finance-payment-recon

Reconciles daily payment transactions against bank statements and flags
discrepancies. Ingests raw payment data from the external payments API into
bronze, then produces a gold-layer reconciliation table for the finance team.

## Owner
@cdo/finance-team

## Inputs
- External payments API — ingested into `cdo_dev.bronze.raw_payments` each run
- `cdo_dev.bronze.raw_payments` — raw payment records landed by the ingest task

## Outputs
- `cdo_dev.gold.payment_recon` — reconciled payments with discrepancy flags (Internal, SLA: available by 06:00 SGT)

## Schedule
Daily at 02:00 SGT (18:00 UTC) — cron `0 18 * * *`

## Rules
- No business logic in notebooks — logic lives in src/finance_payment_recon/
- API ingest task must complete before reconcile task runs (enforced by DAB dependency)
- Never backfill more than 30 days in a single run
- Discrepancy flags must not be removed without finance-team approval
