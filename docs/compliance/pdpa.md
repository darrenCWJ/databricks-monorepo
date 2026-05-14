# PDPA — Personal Data Protection Act mapping

> How the monorepo handles personal data under Singapore's PDPA.

## What counts as personal data

Any data that, alone or with other data we hold, identifies a natural
person. In the catalog, this is anything tagged `pii: true` in the
column metadata.

## The four obligations

### 1. Consent + purpose limitation

- Every dataset's `AGENTS.md` declares the consented purposes.
- New consumers of a personal-data column must trace back to a consent
  record. CODEOWNERS routes the MR through `@cdo/data-governance` for
  review.

### 2. Right to access

- Users can request their data via the public-facing channel (not in
  scope for this repo).
- The platform-team operates a `dsr-access-export` job that produces
  a per-subject export across all relevant catalogs. Lives at
  `apps/pdpa-dsr-access/` (create when first needed).

### 3. Right to correction

- Same flow as access; the export is followed by a correction MR
  against the source-of-truth dataset.
- Downstream silver/gold tables re-compute from the corrected source
  within 24 hours.

### 4. Right to erasure

- Erasure is destructive — we use **column-mask erasure**, not row
  delete: the row stays, identifying columns return null for any
  query after the erasure date.
- The `apps/pdpa-erasure/` job (create when first needed):
  1. Reads erasure requests from the request queue.
  2. Updates a `pdpa_erasure_log` table with subject IDs.
  3. The mask function for every PII column checks the log and returns
     null if the subject is erased.
  4. Original rows are not deleted (preserves audit trail per IM8).

## Required column metadata

Every column with personal data declares:

```yaml
- name: nric
  pii: true
  classification: Restricted
  mask_function: cdo_core.mask_nric    # honours erasure log
  retention_days: 90                    # legal max for non-permitted purposes
  sensitivity: 4
```

## Retention

- **Default retention for PII**: 90 days after purpose served.
- **Permitted longer retention**: tax (7 years), employment (5 years
  after termination), specific legal holds.
- **Retention is enforced** by the platform-team's daily compaction
  job, which `MERGE INTO ... DELETE` rows past retention.

## Cross-border transfers

- Default: all data stays in `ap-southeast-1` (Singapore).
- Exceptions require an MR + `@cdo/data-governance` approval, and a
  data transfer agreement on file.

## Breach response

1. Detect (alert from `system.audit.access_events`).
2. Contain (rotate keys, revoke access, halt jobs).
3. Notify `@cdo/security` + DPO within 1 hour.
4. PDPC notification within 72 hours if the breach is notifiable.
5. Subject notification per DPO's direction.

Full procedure in `runbooks/pdpa-breach.md` (TODO).

## What's NOT covered

- Marketing consent management (the CRM handles that).
- Cookies / web tracking (handled in the public web app, not here).
