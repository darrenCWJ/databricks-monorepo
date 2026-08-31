# Release process (per-project promotion via the release manifest)

> **Changed in September 2026.** Releases are no longer cut as `release/YYYY-MM-DD`
> branches promoted whole. Each project promotes independently, on its own
> schedule. See `branching-strategy.md` for the branch model and
> `docs/superpowers/specs/2026-09-01-modular-release-model-design.md` for rationale.

## What a release is

Two separate things, and keeping them separate is the whole design:

| | What it is | Who creates it |
|---|---|---|
| **A tag** | An immutable name for a tested commit of one project: `v/<domain>-<project>/<YYYY-MM-DD>.<n>` | CI, automatically, when the project goes green on `main` |
| **The manifest** | A declaration of which tag is live in which environment | A human, via MR |

Tags say *what exists*. The manifest says *what is running*. Nobody tags by hand,
and nobody deploys by hand.

## Cadence

There is no fixed cut. Promote when a project is ready. In practice teams settle
into promoting staging most days and prod once a day, but nothing in the system
requires a schedule — and nothing makes one project wait for another.

## Promoting to staging

1. Confirm the project is green on `main` and running in dev. Find its newest tag:

   ```bash
   git tag -l 'v/finance-customer360-etl/*' | sort | tail -3
   ```

2. Open an MR editing exactly one file:

   ```diff
   # release/staging/finance-customer360-etl.yml
    state: active
   -ref: v/finance-customer360-etl/2026-08-17.1
   +ref: v/finance-customer360-etl/2026-08-18.1
   ```

3. CI runs `check-environments` — validates the schema, confirms the ref is a real
   tag, and confirms no transition would drop data.

4. A release approver merges. `reconcile-staging` fires from the protected
   environment and deploys that project only.

## Baking

The bake period flexes with risk; the second approver never does.

| Tier | Bake | When it applies |
|---|---|---|
| **Standard** | 24 hours | The default. Anything touching a schema, a Restricted column, or more than one project. |
| **Expedited** | ~1 hour | Single project, no schema change, no Restricted columns. **CI determines eligibility, not the author.** |
| **Emergency** | Immediate | Production is broken. Deploys now, reviewed within 24 hours, incident record required. |

## Promoting to production

1. Open a second MR, same shape, against `release/prod/<project>.yml`.

2. CI runs `check-environments` **and** `contract-gate`. The contract gate runs
   `check_schema_breaking.py` between the currently-live ref and the proposed one,
   cross-checked against every other project currently `active` in prod. This is
   what makes independent promotion safe: projects in prod run different vintages
   by design, and this catches the case where that becomes a breaking change.

3. A release approver merges. `reconcile-prod` requires one approval in the
   protected environment, **from someone other than whoever triggered the
   pipeline** — GitLab enforces the SOC2 segregation of duties.

4. `audit_log.py` records who, what, from-ref, to-ref, and approver to the WORM
   bucket.

Only the named project deploys. Every other project's prod state is untouched.

## Promoting several projects at once

One MR may edit several files under `release/prod/`. Use this when a batch is
genuinely ready together — it saves approver round-trips. Do **not** batch to work
around approver availability; that reintroduces the coupling this model removes.

## Pausing

To stop a project running in an environment without removing it:

```diff
# release/prod/supplier-spend-report.yml
-state: active
+state: paused
+reason: awaiting FY27 cost-centre migration
+ticket: CHG-14882
+review_by: 2026-10-01
```

Resources stay deployed; the schedule stops. No redeploy, no cluster, seconds to
apply and seconds to reverse. `review_by` is mandatory — CI warns when it expires
so nothing sits paused and forgotten.

For `streaming` projects, set `review_by` **below the source's retention window**
(Kafka, Kinesis, Autoloader). Resume past that point and the checkpoint is
unrecoverable.

## Retiring

```diff
-state: active
+state: retired
+retired_on: 2026-08-20
+reason: superseded by supplier/spend-report
+ticket: CHG-14201
+data_disposition: retained
```

Workspace resources are removed. **Data is retained.** The project folder stays in
the repo and the manifest row stays permanently as the record.

The reconciler generates the destroy plan, inspects it, and **refuses** if it
would drop any table. Dropping data is `purged` — not reachable from a manifest
edit, and requiring its own change ticket and runbook.

## Rolling back

Same operation as rolling forward. Point the ref at an older tag:

```diff
-ref: v/finance-customer360-etl/2026-08-18.1
+ref: v/finance-customer360-etl/2026-08-17.1
```

Or, to stop the bleeding first, set `state: paused` — seconds, no redeploy — then
decide on the code separately.

**Rolling back code is not rolling back data.** If a bad job wrote to a production
table, re-deploying the old code fixes the pipeline and leaves the table wrong.
Delta time travel is how you undo the write, and it is an explicit, approved step:

```sql
RESTORE TABLE <table> TO VERSION AS OF <n>;
```

`rollback_depth_days` in the manifest sets both how far back we keep tags and the
Delta `deletedFileRetentionDuration`, so you can never have a ref that restores
code perfectly against data you can no longer restore.

## Verifying what is actually live

The manifest is a claim until it is checked. Every deployed resource is stamped
with `cdo_release_ref` and `cdo_git_sha`:

```bash
python tools/scripts/reconcile.py --check --target prod
```

This runs nightly and reports any drift between the manifest and the workspace —
including anything changed by hand in the Databricks UI.

For a human-readable view of everything, everywhere:

```bash
cat release/STATE.md      # generated by CI, never edited by hand
```

## Audit

`git log -p release/prod/` is the complete production change history: what
changed, when, and who approved it. Combined with the WORM deploy trail from
`audit_log.py` and the immutable `v/` tags, that is the evidence set.

## See also

- `branching-strategy.md` — branches, merge trains, hotfixes, rollback
- `docs/compliance/soc2.md` — how these map to SOC2 controls
- `docs/runbooks/access-control.md` — the four grant layers
- `docs/superpowers/specs/2026-09-01-modular-release-model-design.md` — full design
