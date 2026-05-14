# IM8 — Tier 1 control mapping

> How the monorepo maps to IM8 (Singapore government Instruction Manual
> on Infocomm Technology and Smart Systems Management) Tier 1 controls.
> Authoritative source: IM8 v2024. This document is a quick reference,
> not a substitute for reading the standard.

## Classification vocabulary

| IM8 tier | Examples | Storage in this monorepo |
|---|---|---|
| Official-Open | Public datasets, published metrics | `cdo_<env>.public.*` |
| Official-Closed | Internal KPIs, supplier non-financials | `cdo_<env>.silver.*`, `cdo_<env>.gold.*` |
| Restricted | PII, supplier financials, draft policy | `cdo_<env>.restricted.*`, masked at column level |
| Confidential | Cleared-personnel records | `cdo_<env>.confidential.*`, firewalled to cleared groups only |

## Required behaviours

| Control | How we satisfy it |
|---|---|
| **A.1 Classification on every column** | `bundle.yml#tables#<name>#columns` — every column has `classification` + `sensitivity` + `retention_days`. Pre-commit blocks the MR if missing. |
| **A.2 Mask Restricted data** | Column masks via `mask_function` in the column definition. Default-allow only for the project's own SP. |
| **A.3 No Restricted data in dev** | Dev catalog uses synthetic data only. Staging/prod use real-masked. Hard-enforced by the catalog topology in `terraform-databricks/`. |
| **A.4 Retention** | `retention_days` per column. Daily compaction job (in platform-team) removes rows past retention. |
| **A.5 Audit access to Restricted** | Every SELECT on `cdo_<env>.restricted.*` logs to `system.audit.access_events`. Logs go to WORM S3, 7-year retention. |
| **A.6 Encryption in transit** | TLS 1.2+ enforced on the Databricks workspace and on Lakebase. No HTTP endpoints anywhere. |
| **A.7 Encryption at rest** | S3 SSE-KMS with customer-managed key. Lakebase encrypted at rest. |
| **A.8 Backup + DR** | Delta time-travel for 30 days. S3 versioning + cross-region replication to ap-southeast-3. |
| **B.1 Change management** | Every MR has a change-ticket ID. SOC2-style segregation of duties between merger and prod deployer. |
| **B.2 Approval evidence** | CODEOWNERS + MR template. Approval lives in GitLab MR history, queried via `tools/scripts/audit_log.py`. |
| **C.1 Awareness training** | All engineers complete IM8 Tier 1 awareness annually. Tracked in HR system. |
| **C.2 Incident response** | `runbooks/security-incident.md` (TODO). PagerDuty rotation. Disclosure timeline coordinated with `@cdo/security`. |

## Annual review

Platform team re-validates this mapping every January, after IM8 updates
are published.

## What's NOT covered

- Physical security (data centre access). AWS GCC handles this; not in
  scope for the monorepo.
- Personnel clearance procedures. HR runs these; we just consume the
  cleared-group output.
