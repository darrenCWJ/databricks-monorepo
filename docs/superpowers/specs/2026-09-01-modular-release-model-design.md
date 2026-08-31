# Modular release model for the CDO monorepo

- **Status:** draft for review
- **Date:** 2026-09-01
- **Supersedes:** the release-branch model in `docs/runbooks/release-process.md`
- **Extends:** `CDO-Branching-and-Release-Model.pptx` (tags-not-branches, four tiers)

## Problem

One repo, many teams, independent business pipelines. The documented model makes
the **git branch the release unit** (`release/YYYY-MM-DD` promoted whole through
staging then prod). In a monorepo that is a release train: everything boards at
once, and one unready project holds the doors.

Two concrete failures in the current design:

1. **A tag is a point on a line.** Tagging commit N for prod ships everything
   merged before N. `affected.py` scopes the deploy *work*; it cannot exclude
   something already merged. The real case is work that is merged, reviewed and
   green but not *business*-ready. Green != ready.
2. **Shared libs are a workspace-global singleton.** *(Settled 2026-09-01 by
   ADR-0006: libs now ship as wheels built by the consuming bundle.)* `.claude/rules/lib-imports.md`
   and `docs/adr/0003-shared-library-layout.md` mandate
   `sys.path.append("/Workspace/Repos/shared/mono-dev/libs/<lib>/src")`. One path,
   one copy per workspace. Promoting one project moves the lib for every project,
   silently, without those projects being deployed or tested.

## Design: three control planes

They change at different rates and have different approvers. Conflating them is
the failure mode.

| Plane | Artifact | Rate | Approver | Answers |
|---|---|---|---|---|
| Code | `main` + per-project tags | many/day | CODEOWNERS | what is possible |
| Release | `release/{dev,staging,prod}/<project>.yml` | few/day | `@cdo-release-approvers` | what is where, and running |
| Infra | `infra/` Terraform | weekly | platform + governance | what code may touch |

A fourth plane — **data** — exists and git cannot describe it. Delta table
contents are why rollback is never one action.

Infra stays in Terraform: it has its own reconciler and state, and two
reconcilers over the same resources will fight.

## The release manifest

**One file per project per environment.** A generated `release/STATE.md` gives
the single-glance view.

```yaml
# release/prod/finance-customer360-etl.yml
state: active
ref: v/finance-customer360-etl/2026-08-17.1
```
```yaml
# release/prod/supplier-spend-report.yml
state: paused
ref: v/supplier-spend-report/2026-07-30.2
reason: awaiting FY27 cost-centre migration
ticket: CHG-14882
review_by: 2026-10-01
```
```yaml
# release/prod/legacy-spend-etl-v1.yml
state: retired
retired_on: 2026-08-20
reason: superseded by supplier/spend-report
ticket: CHG-14201
data_disposition: retained
```

`rollback_depth_days` and other cross-cutting policy live in `release/policy.yml`,
which changes rarely.

`release/dev/<project>.yml` uses `ref: main` — dev tracks the tip and needs no
manifest MR. Staging and prod pin tags and move only by MR.

### Why one file per project, not one file per environment

An earlier draft used a single `release/prod.yml` holding every project. That
makes the manifest the one file every promotion edits — precisely the shape that
generates merge conflicts between teams who otherwise never touch the same code.
In a monorepo with directory-disjoint ownership, almost all conflicts come from a
handful of shared files; the fix is to stop having them.

One file per project means two teams promoting simultaneously edit different
files and cannot conflict. The single-pane view is preserved by generating
`release/STATE.md` in CI rather than by authoring one big file. It also lets
CODEOWNERS route per environment *and* per project if that is ever wanted.

- **Tags are created by CI**, automatically, when a project goes green on `main`.
  Nobody tags by hand. Tags are cheap immutable names, not decisions.
- **The deploy trigger is merging a manifest change**, not pushing a tag. This is
  the correction to the tag-triggered model: a global tag promotes temporally, a
  manifest promotes per project.
- **`git log -p release/prod/` is the audit trail** — timestamped,
  approver-attributed, complete, in one file. Stronger evidence than tags alone,
  which record what *could* have shipped.

## State machine

| State | Resources | Schedule | Data | Cost to change |
|---|---|---|---|---|
| `active` | present | UNPAUSED | live | — |
| `paused` | present | PAUSED | retained | one field, no redeploy |
| `retired` | removed | n/a | **retained** | `bundle destroy --select` |
| `purged` | removed | n/a | dropped | separate runbook, separate approver |

**Invariant: no state transition may delete data.** `retired` removes jobs and
pipelines, never tables. The project folder stays in the repo with full history
and the manifest row stays permanently as the record of what was run and why it
stopped. Turning it back on is one MR.

`purged` is never reachable from a manifest edit. It requires its own change
ticket and runbook.

### Per-function-type semantics

The state machine is shared; the mechanism is per type.

| Type | `paused` mechanism | `retired` risk | Failure mode when paused |
|---|---|---|---|
| `pipeline` | `schedule.pause_status: PAUSED` | low | **silent** — stale tables, no error |
| `streaming` | `continuous: false` | low | silent + checkpoint decay |
| `capture` (DLT/CDC) | stop pipeline | **DLT delete can drop managed tables** | silent |
| `app` | stop app compute | low | loud — users see it down |
| `dashboard` | revoke publish | low | loud |
| `api` | scale to zero | low | loud — callers error |
| `sync` (Lakebase) | pause sync | Postgres target table | silent |

Three consequences:

- **Pipelines fail silently; apps fail loudly.** A paused pipeline hands
  downstream consumers yesterday's rows and nothing errors. Every paused pipeline
  must emit a freshness signal its consumers can see. Apps need the opposite: a
  maintenance banner rather than 503s.
- **Paused streams expire.** Resuming past source retention (Kafka, Kinesis,
  Autoloader) leaves an unrecoverable checkpoint. `review_by` is mandatory for
  `streaming` and must default below source retention, not to a business date.
- **`retired` must be code-enforced.** The reconciler plans the destroy, inspects
  it for table deletions, and REFUSES — not warns — if any appear.

## Rollback

| Kind | Mechanism | Time | Automated |
|---|---|---|---|
| Config — stop the bleeding | set `state: paused` | seconds | yes, no redeploy |
| Code — bad logic shipped | point `ref` at previous tag | minutes | yes |
| Data — bad rows written | `RESTORE TABLE ... TO VERSION AS OF n` | deliberate | **never** |

Rollback and roll-forward are the same operation: edit a ref. There is no
separate emergency path to get wrong at 3am.

**Retention trap.** Delta `deletedFileRetentionDuration` defaults to 7 days and
VACUUM enforces it. A manifest offering 21 days of code rollback against tables
that time-travel 7 gives a `ref` that restores code perfectly against data that
cannot be restored. `rollback_depth_days` is declared once at the top of the
manifest; the bundle template reads it for table properties and CI fails any
table whose retention is below it.

## Branches

| Branch | Lifetime | Protected | Purpose |
|---|---|---|---|
| `main` | permanent | yes | the only trunk |
| `feature/<team>-<desc>` | days | no | all normal work |
| `hotfix/<desc>` | hours | no | urgent fix, expedited review |
| `recovery/<tag>` | hours, rare | no | only when `main` is not shippable |

No `release/*`, no `develop`, no environment branches. Steady-state branch count
is approximately the number of engineers mid-task and does not grow. Tags grow
~250/year, live on their own page, need no cleanup, and are the rollback targets.

**Breaking change to existing docs:** `CLAUDE.md` and
`docs/runbooks/branching-strategy.md` both mandate `hotfix/<ticket>` branched off
the active `release/*`. With no release branches, hotfixes branch off `main`.
Both files must be updated or agents will keep generating the old flow.

### History

Fast-forward merge, squash required: one MR becomes one commit on `main`. A tag
then points at exactly one reviewed unit, and rollback granularity equals review
granularity. Linear history also makes `git diff BASE...HEAD` in `affected.py`
and "what changed between prod ref A and B" unambiguous; merge commits make
three-dot diffs subtly wrong.

Merge trains with fast-forward merge rebase the source branch automatically.
Engineers rebase manually only on conflict. `main` is never rebased.

## Testing before merge

| Tier | What | Cost | Deploys |
|---|---|---|---|
| Local | `make lint test P=...` + pre-commit | seconds | no |
| CI on push | lint, mypy, pytest, bundle-validate, security | 3-5 min | no |
| Branch sandbox | `make bundle-deploy P=... T=sandbox` | a cluster | yes, into `cdo_dev.<project>_<branch-slug>` |

The sandbox is a distinct **schema** in the shared dev workspace. Databricks dev
mode prefixes resource names but does not isolate schemas — without explicit
schema parameterisation in the bundle template, two engineers on one project
overwrite each other's tables. This is the one genuine blocker.

## Maintaining dev

- Sandbox schema dropped automatically when the MR merges or closes, via GitLab
  environment `on_stop` (`auto_stop_in: 3 days` as backstop).
- Nightly `reconcile.py --check --target dev` finds workspace resources with no
  manifest row.
- The dev catalog is declared **disposable** and documented as rebuildable.
- Dev data is a subset or synthetic, refreshed on a stated cadence.

Open conflict: `databricks.yml` sets dev `schedule_pause_status: PAUSED` while the
Cowork deck describes dev as "shared + scheduled". Recommendation: keep dev
paused by default with per-project opt-in. Unattended dev jobs are the most
common source of surprise cloud spend.

## Repo layout

```
release/
  policy.yml       rollback_depth_days and other cross-cutting policy
  schema.json      validates every manifest file
  dev/<project>.yml       CODEOWNERS -> the team that owns the project
  staging/<project>.yml   CODEOWNERS -> @cdo-release-approvers
  prod/<project>.yml      CODEOWNERS -> @cdo-release-approvers
  STATE.md         generated, read-only, single pane
platform/
  targets.yml      one copy of dev/staging/prod workspace + variable defs
projects/<domain>/<name>/
  databricks.yml   per-project bundle root; target block generated from platform/
tools/scripts/
  reconcile.py           manifest -> workspace actions
  check_environments.py  manifest validation (pre-commit + CI)
  contract_gate.py       schema-breaking check vs projects active in prod
  render_state.py        generates release/STATE.md
```

DAB `include:` may not resolve paths above the bundle root. Rather than rely on
it, generate each project's target block from `platform/targets.yml` via
`make targets`, with `make check-targets` failing CI on drift — the same pattern
already used for `make data-map` / `make check-data-map`.

## The reconciler

The only thing that touches staging or prod. No human runs `bundle deploy -t prod`.

```
reconcile.py --target prod
  for each project:
    desired <- release/prod/<project>.yml
    actual  <- workspace (jobs API + resource tags)
    plan the diff, then:
      absent  -> active   git checkout <ref>; bundle deploy -t prod; unpause
      active  -> paused   pause via API, no redeploy
      paused  -> active   unpause
      ref changed         git checkout <ref>; bundle deploy -t prod
      *       -> retired  bundle destroy --select ...   REFUSE if plan drops tables
  audit_log.py <- who, what, from-ref, to-ref, approver
```

Every deployed resource is stamped with `cdo_release_ref` and `cdo_git_sha` so
actual state is queryable and UI drift is detectable. `reconcile.py --check` runs
nightly. Without this the manifest is a claim; with it, a verified fact.

`databricks bundle deploy --select` filters the plan to named resources, and per
the CLI source non-selected resources cannot receive Delete actions under
`--select`. It requires the direct deployment engine (rejected on the terraform
engine). Verify against the pinned CLI version before relying on it.

## CI

```
stages: [lint, affected, test, validate, security,
         sandbox, release, deploy-dev, reconcile, drift]
```

| Job | feature | MR/train | main | manifest MR | nightly |
|---|---|---|---|---|---|
| lint, compute-affected, test, bundle-validate, security | y | y | y | y | |
| `check-environments` | | | | y | y |
| `contract-gate` | | | | y (prod) | |
| `sandbox-deploy` (manual) | y | y | | | |
| `sandbox-teardown` (on env stop) | y | y | | | |
| `tag-release` | | | y | | |
| `deploy-dev` | | | y | | |
| `reconcile-staging` / `reconcile-prod` (manual) | | | | y | |
| `drift-check` | | | | | y |

Sandbox lifecycle uses GitLab environments natively:

```yaml
sandbox-deploy:
  stage: sandbox
  when: manual
  environment:
    name: sandbox/$CI_COMMIT_REF_SLUG
    on_stop: sandbox-teardown
    auto_stop_in: 3 days
```

### Known fixes required

- **`affected.py` diff base is wrong under merge trains.** CI uses
  `origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME`; merge trains run against a ref
  including preceding MRs, so the base over-reports. Use
  `$CI_MERGE_REQUEST_DIFF_BASE_SHA`.
- **CI installs `databricks-cli` via pip** — that is the legacy Python CLI. DAB
  needs the modern Go CLI, pinned.
- **"Skipped pipelines are considered successful" must be Off**, or affected-only
  skips wave through a red MR.

## GitLab settings

Step-by-step configuration, verification tests and the governance control map
live in `docs/runbooks/gitlab-setup-release-model.md`. Summary:

**Merge requests:** fast-forward merge; merge trains on; merged results pipelines
on; squash **required**; pipelines must succeed; all threads resolved; delete
source branch by default; skipped-pipelines-successful **off**.

**Approvals:** CODEOWNER approval required on protected branches; prevent approval
by author; prevent approval by users who add commits; remove all approvals when
commits added; prevent editing approval rules in MRs.

**Protected branches:** `main` — push: no one; merge: maintainers; force push off;
code owner approval required.

**Protected tags:** `v/*` — create: maintainers and the CI token only.

**Protected environments:** `dev` — CI service account, 0 approvals. `staging` —
`@cdo-release-approvers`, 0 approvals. `production` — `@cdo-release-approvers`,
**1 approval, not the pipeline triggerer**. That is where SOC2 segregation of
duties lands, enforced by the tool.

**Push rules** (Premium) enforce the branch-name and commit-message conventions at
the pre-receive hook, and `deny_delete_tag` protects the `v/` tags that are
simultaneously our rollback targets and our audit evidence.

## Ordering and throughput

Merge trains run **parallel** merged-results pipelines: each queued MR is tested
against the target plus every change ahead of it, and merges once its own pipeline
passes and all preceding MRs have merged. This is the speculative execution
described in Uber's SubmitQueue paper, so throughput is not capped at one MR per
pipeline duration.

A failed train pipeline drops that MR and immediately restarts pipelines for
everything behind it; the failed pipeline cannot be retried directly. Two
consequences: put `retry:` on network-dependent jobs so flakes do not cost the
queue, and keep MRs small.

Manifest promotions carry no ordering constraint — two teams promoting at once
edit different files. The one genuine cross-project ordering constraint is data:
promoting a producer can break a consumer running an older vintage. That is what
`contract-gate` exists to catch.

Fast-forward merge with merge trains requires GitLab 16.4+ Premium/Ultimate; on
self-managed it may need the `fast_forward_merge_trains_support` feature flag.
Verify before adopting.

## Who holds what

| Role | Owns | Approves | Never does |
|---|---|---|---|
| Data engineer | feature branch, sandbox schema, tests, contracts, `release/dev/` for their own projects | dev-only manifest changes in their own team | deploys to staging or prod |
| CODEOWNER | code quality in their folder | MRs into `main` | approves own MR |
| Release approver | `release/staging/`, `release/prod/` | promotions, pauses, retires | approves a pipeline they triggered |
| Platform team | `platform/`, `infra/`, the reconciler | infra and CI changes | edits a team's project code |

## Open decisions

1. `retired` — automated destroy with a refusal guard, or generate the destroy
   plan into the MR and have a human execute? Given DLT can drop tables, the
   manual variant is the safer first version.
2. `@cdo-release-approvers` is two people. Per-project promotion means more,
   smaller MRs, so two approvers jams sooner than under a weekly train.
   Mitigations to build in from day one: batch promotions (one MR bumping several
   ready projects) and CI-determined auto-approval for the expedited tier
   (single bundle, no schema change, no Restricted columns).
3. Dev ownership is settled: teams manage `release/dev/` for their own projects.
   The CODEOWNERS gate is the merge into `main`, not a second gate on a team's own
   sandbox environment.
4. Lib versioning — **settled**. `docs/adr/0006-libs-as-bundle-built-wheels.md`:
   libraries are built as wheels by the consuming bundle from its own pinned ref,
   so each project carries its own copy. No registry needed, no version pin — the
   git ref is the version. Remaining sub-question: Databricks Apps and serverless
   resolve dependencies from `requirements.txt` and cannot use task `libraries`;
   that needs its own answer before the first `app` or `api` project ships.
