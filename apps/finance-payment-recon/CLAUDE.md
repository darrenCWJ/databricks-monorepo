# finance-payment-recon — Claude Context

## What this app does
Reconciles daily payment transactions against bank statements and flags
discrepancies. Ingests raw payment data from the external payments API into
bronze, then produces a gold-layer reconciliation table for the finance team.

## Domain rules (never violate these)
- Never remove or weaken discrepancy flags without explicit approval from @cdo/finance-team
- Never backfill more than 30 days in a single run
- API ingest (task 1) must always complete before reconcile (task 2) — do not merge tasks
- Gold output `payment_recon` is consumed downstream — schema changes require a migration PR

## Data contracts
| Table | Classification | SLA | Owner |
|---|---|---|---|
| `bronze.raw_payments` | Internal | Landed by 02:30 SGT | @cdo/finance-team |
| `gold.payment_recon` | Internal | Available by 06:00 SGT | @cdo/finance-team |

## Discrepancy logic
- Threshold: `DISCREPANCY_THRESHOLD = 0.01` in `reconcile.py`
- Any change to this value is a contractual change — update AGENTS.md and notify consumers

## How to run locally
```bash
make test P=apps/finance-payment-recon
make lint P=apps/finance-payment-recon
make bundle-validate P=apps/finance-payment-recon
```

## Key files
- `src/finance_payment_recon/ingest.py` — API fetch + bronze write
- `src/finance_payment_recon/reconcile.py` — discrepancy logic + gold write
- `notebooks/01_api_ingest.py` — thin shim for ingest task
- `notebooks/02_reconcile.py` — thin shim for reconcile task

## Gotchas
- `_fetch_from_api()` in ingest.py is a stub — replace with real API client before first deploy
- Gold uses `replaceWhere` on `reconciliation_date` — safe for daily reruns, not range backfills
