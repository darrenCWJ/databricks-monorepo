# Data Architecture

Auto-generated from `apps/*/AGENTS.md`. Do not edit manually.
Regenerate with: `make data-map`

## Project Catalogue

| Project | Folder | Owner | Reads from | Writes to | Schedule |
|---------|--------|-------|------------|-----------|----------|
| finance-payment-recon | `apps/finance-payment-recon` | @cdo/finance-team | External payments API — ingested into `cdo_dev.bronze.raw_payments` each run, `cdo_dev.bronze.raw_payments` — raw payment records landed by the ingest task | `cdo_dev.gold.payment_recon` — reconciled payments with discrepancy flags (Internal, SLA: available by 06:00 SGT) | Daily at 02:00 SGT (18:00 UTC) — cron `0 18 * * *` |
