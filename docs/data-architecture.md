# Data Architecture

Auto-generated from `apps/*/AGENTS.md`. Do not edit manually.
Regenerate with: `make data-map`

## Project Catalogue

| Project | Folder | Owner | Reads from | Writes to | Schedule |
|---------|--------|-------|------------|-----------|----------|
| demo-ingest-medallion | `apps/demo-ingest-medallion` | @cdo/platform-team | `landing.raw_orders`, `landing.raw_customers` | `bronze.orders`, `silver.orders_clean`, `gold.revenue_daily` | Daily 02:00 SGT |
