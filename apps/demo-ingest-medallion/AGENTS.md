# demo-ingest-medallion

Medallion architecture demo pipeline. Ingests raw sales orders from the
landing zone, cleans and validates them into a silver layer, then produces
gold-layer revenue aggregates for downstream dashboards and dbt models.

## Owner
@cdo/platform-team

## Inputs
- `cdo_dev.landing.raw_orders` — raw CSV-sourced order records, append-only
- `cdo_dev.landing.raw_customers` — raw customer dimension, full-refresh daily

## Outputs
- `cdo_dev.bronze.orders` — unmodified source records with ingestion metadata
- `cdo_dev.silver.orders_clean` — validated, deduplicated orders with schema enforcement
- `cdo_dev.gold.revenue_daily` — daily revenue aggregates by region and product

## Schedule
Daily at 02:00 SGT. Bronze runs first; silver and gold are downstream tasks in the same job.

## Rules
- Never overwrite bronze — append only, partition by ingestion date.
- Silver deduplication key is `order_id`. Duplicate rows are quarantined, not dropped.
- Gold aggregates are full-refresh; downstream consumers must tolerate a short unavailability window.
- No business logic in notebooks — logic lives in `src/demo_ingest_medallion/`.
