# Data contracts

## What's a data contract here

A **data contract** is the agreement between a producing project and
its consumers. It says: *this table has this schema, written by this
job, on this schedule, with these classifications and SLAs.*

The contract lives in the producing app's `AGENTS.md` and is enforced
by:

- Pre-commit hooks on the producer (schema must match the contract).
- CI tests on consumers (the consumer's read must match the documented
  schema).
- Unity Catalog table properties (machine-readable contract metadata).

## Required contract fields

Every Delta table produced by an app declares, in its `bundle.yml`:

```yaml
resources:
  tables:
    silver_payments:
      schema: cdo_${var.env}.silver
      columns:
        - {name: txn_id,      type: string,    pii: false,
            classification: Official-Closed, retention_days: 730}
        - {name: customer_id, type: string,    pii: true,
            classification: Restricted,       retention_days: 90,
            mask_function: cdo_core.mask_id}
        - {name: amount_sgd,  type: decimal(18,2), pii: false,
            classification: Official-Closed, retention_days: 730}
      primary_key: txn_id
      sla:
        freshness: 24h
        availability: 99.5%
```

## Producer responsibilities

- **Don't break schema without 14 days notice.** Additive changes are
  always fine; removals or renames trigger an ADR + the deprecation
  cycle in `data-modeling.md`.
- **Hit the SLA.** Missing freshness > 1.5× allowed triggers a P2 alert.
- **Notify @cdo/data-governance** if the classification changes.

## Consumer responsibilities

- **Don't `select *`.** Name the columns you depend on; that's your
  half of the contract.
- **Test the contract.** A consumer's integration tests assert the
  columns and types they read.
- **Subscribe to the producer's MR feed** for the project — change
  notifications go through CODEOWNERS.

## When things go wrong

- **Producer breaks the schema unexpectedly.** Consumer opens a P2
  incident; producer rolls back or hotfixes within 4 hours.
- **Consumer reads a column it didn't declare.** Producer can rename
  / remove without notice; on consumer.
- **SLA missed.** Producer documents the failure in `system.audit`
  and pages the on-call.

## Tooling

- `just where-is <table>` — which app produces this table?
- `tools/scripts/contract_check.py` — pre-commit gate that verifies
  every Delta write matches its declared contract.
- `tools/scripts/contract_diff.py` — show schema changes in a producer's
  MR diff (for the consumer-side CODEOWNERS to review).
