# Runbook: branching strategy + environment promotion

Every engineer needs to know four things on day one:

1. What branch do I create?
2. How do I test before I merge?
3. What happens when someone else pushes to `main` while I'm working?
4. How does my code reach prod — and how do I stop it if it shouldn't?

This runbook answers each.

> **Changed in September 2026.** There are no longer any `release/*` branches.
> A release is a per-project immutable tag, assigned to an environment by a
> version-controlled manifest. See `docs/superpowers/specs/2026-09-01-modular-release-model-design.md`
> for the rationale, and `release-process.md` for the promotion procedure.

## The branches you'll touch

| Branch | Purpose | Lifetime | Protected |
|---|---|---|---|
| `main` | The only trunk. Always green, auto-deploys to dev. | Permanent | Yes |
| `feature/<team>-<desc>` | Your day-to-day work. One feature, one branch. | Days | No |
| `hotfix/<desc>` | Urgent fix. Same flow, expedited review. | Hours | No |
| `recovery/<tag>` | Rare. Branched from a `v/` tag, only when `main` holds something unsafe to ship. | Hours | No |

Four kinds, three of them ephemeral. Steady-state branch count is roughly the
number of engineers mid-task — it does not grow.

**There are no `release/*` branches.** Nothing to cut, nothing to cherry-pick
into, nothing to keep for twelve months, nothing to clean up.

### Naming convention

Format: `feature/<team-prefix>-<short-description>`

| Good | Bad |
|---|---|
| `feature/finance-budget-fix` | `feature/fix` (no team prefix, vague) |
| `feature/supplier-spend-v2` | `feature/john-tuesday` (personal naming) |
| `feature/customer360-add-segment` | `feature/CHG-12345` (ticket as branch name; cite it in the MR instead) |

The `<team-prefix>` matches `projects/<domain>/`. It makes branch lists scannable
and routes CODEOWNERS.

## Releases are tags, not branches

When a project goes green on `main`, CI creates an immutable tag:

```
v/<domain>-<project>/<YYYY-MM-DD>.<n>
v/finance-customer360-etl/2026-08-17.1
```

**Nobody tags by hand.** Tags are cheap immutable names, not decisions. They live
on the Tags page, cost nothing to keep, and are your rollback targets. Roughly
250 a year.

Which tag is live in which environment is declared in the release manifest, one
file per project per environment:

```
release/dev/finance-customer360-etl.yml       # ref: main — tracks the tip
release/staging/finance-customer360-etl.yml   # ref: v/finance-customer360-etl/2026-08-18.1
release/prod/finance-customer360-etl.yml      # ref: v/finance-customer360-etl/2026-08-17.1
```

Promotion is an MR that changes one of those files. **One project moving does not
move any other.** Finance shipping today does not drag Supplier's half-finished
work along with it.

## Answering the staleness problem

> *"I branched off `main`, someone else merged, now I'm behind and have to rebase.
> With a whole team doing this, we'd rebase constantly."*

Three things make this a non-problem. In order of how much they matter:

### 1. The merge train rebases for you

This is the industry-standard answer and we already have it switched on. When you
put an MR on the train, GitLab builds a temporary ref of `main` + every MR ahead
of yours in the queue + yours, runs the pipeline against *that*, and merges only
if it is green. If it fails, your MR drops off the train and only you have to fix
anything.

**You should never rebase manually because `main` moved.** Only rebase when git
reports a genuine textual conflict. If people are hand-rebasing for staleness,
the train is misconfigured — see the settings below.

This is the same design as Uber's SubmitQueue, which took their monorepo mainline
from green 52% of the time to green always, at thousands of commits a day.

### 2. Most conflicts in a monorepo are false conflicts

Finance works in `projects/finance/`. Supplier works in `projects/supplier/`.
They never touch the same file, so git merges them cleanly with no human input.

Staleness pain concentrates entirely in files *everyone* edits. We have designed
those out:

| Shared file | Why it used to conflict | How it is handled |
|---|---|---|
| Release manifest | Every promotion edits it | **One file per project** — `release/prod/<project>.yml`. Two teams promoting at once touch different files. Zero conflicts, ever. |
| `pyproject.toml` workspace members | Every new project appends a line | Globs: `members = ["projects/*/*", "libs/*"]`. Nothing to append. |
| `CODEOWNERS` | New project = new line | Team wildcards (`/projects/finance-*/`) already cover new projects. |
| `docs/data-architecture.md` | Generated but committed | The conflict is meaningless. Take either side, run `make data-map`, commit. |

### 3. Short branches don't go stale

A branch open three hours almost never conflicts. A branch open two weeks always
does. The DORA research draws the line at **under one day**, and finds elite
performers are 2.3× more likely to work this way.

So the real fix is smaller MRs, not better rebasing. If a branch has been open
more than a couple of days, split it.

### Local ergonomics

Set these once and forget them:

```bash
git config --global pull.rebase true        # never create accidental merge commits
git config --global rebase.autosquash true  # honour `git commit --fixup`
git config --global rerere.enabled true     # remember how you resolved a conflict
```

`rerere` ("reuse recorded resolution") is the underrated one — if you do hit the
same conflict twice across a rebase, git resolves it for you the second time.

### The GitLab settings that make this work

| Setting | Value | Why it matters here |
|---|---|---|
| Merge method | Fast-forward merge | Linear `main`; unambiguous diff ranges for `affected.py` and rollback |
| Merge trains | On | The train does the rebasing |
| Merged results pipelines | On | Prerequisite for trains |
| Squash commits | Require | One MR = one commit = one rollback unit |
| Delete source branch by default | On | Keeps the branch list short |
| Skipped pipelines considered successful | **Off** | Otherwise affected-only skips wave through a red MR |

Fast-forward merge combined with merge trains needs GitLab 16.4+ Premium or
Ultimate; on self-managed it may require the `fast_forward_merge_trains_support`
feature flag. Confirm before relying on it.

## How environments map

| Environment | Catalog | Moves when | Approver |
|---|---|---|---|
| **Branch sandbox** | `cdo_dev.<project>_<branch-slug>` | You run the manual job | None — it's yours |
| **dev** | `cdo_dev` | Automatic on merge to `main` | None (review already happened) |
| **staging** | `cdo_staging` | MR bumping `release/staging/<project>.yml` | Release approver |
| **prod** | `cdo_prod` | MR bumping `release/prod/<project>.yml` | A *different* approver (SOC2) |

Dev is **pushed**; staging and prod are **pulled**. That asymmetry is deliberate —
it makes dev fast and production deliberate.

## Day-to-day: the full loop

```bash
git checkout main && git pull
git checkout -b feature/finance-budget-fix

# ... work ...
make lint P=projects/finance/budget
make test P=projects/finance/budget

# prove it for real, in your own schema
make bundle-deploy P=projects/finance/budget T=sandbox

git push -u origin feature/finance-budget-fix
```

Open an MR targeting `main`. CI runs affected-only, 3–5 minutes. CODEOWNERS routes
the review. Put it on the merge train; it rebases and merges itself.

Your sandbox schema is dropped automatically when the MR merges or closes.

## What happens when the MR merges

```
merge to main
   ↓
compute-affected — only the bundles your diff touched
   ↓
deploy-dev — databricks bundle deploy -t dev
   ↓
tag-release — CI creates v/<project>/<date>.<n>
   ↓
audit_log.py records who, what, when
```

No human intervention. Dev is the shared integration picture.

## Promoting to staging and prod

See `release-process.md`. In short: two small MRs against the manifest, each a
few lines, each approved by a release approver — and the prod one by someone
other than whoever triggered the pipeline.

## Hotfixes

**The normal path (~95%).** Fix on `main` like anything else:

```bash
git checkout main && git pull
git checkout -b hotfix/budget-null-costcentre
# ... fix, expedited CODEOWNER review, same CI ...
```

Merge. It deploys to dev and CI tags it. Bump `release/prod/<project>.yml` to
that tag under the emergency tier. **Because you fixed on `main`, the fix is in
every future release automatically. There is no cherry-pick, ever.**

**The exception path (a few times a year)** — only when `main` contains something
that is not safe to ship yet:

```bash
git checkout -b recovery/v-finance-budget-2026-08-17.1 v/finance-budget/2026-08-17.1
# ... fix, review, CI tags the result ...
```

Bump `release/prod/` to the new tag. Then **merge the same fix back to `main`** —
this is the step people forget, and skipping it means the bug returns on the next
promotion.

## Stopping and rolling back

Three different things, and conflating them makes an incident worse:

| You want to | Do this | Takes |
|---|---|---|
| Stop a running job now | Set `state: paused` in `release/prod/<project>.yml` | Seconds — no redeploy |
| Undo bad code | Point `ref` at the previous tag | Minutes — automated |
| Undo bad rows | `RESTORE TABLE … TO VERSION AS OF <n>` | Deliberate — runbook + approver |

Rollback and roll-forward are the same operation: edit a ref. There is no separate
emergency path to get wrong at 3am.

**Retention trap:** Delta's deleted-file retention defaults to 7 days and VACUUM
enforces it. `rollback_depth_days` in the manifest sets both the tag retention and
the table retention so they cannot drift apart.

## Turning a project off

| State | Resources | Schedule | Data |
|---|---|---|---|
| `active` | present | running | live |
| `paused` | present | stopped | retained |
| `retired` | removed | n/a | **retained** |

**No state transition may delete data.** `retired` removes jobs and pipelines,
never tables. The project folder stays in the repo with its full history and the
manifest row stays permanently as the record of what ran and why it stopped.
Turning it back on is one MR.

Use `paused` when something is merged but not business-ready — awaiting a
migration, a cutover window, a stakeholder sign-off. Every pause carries a
`reason`, a `ticket`, and a `review_by` date that CI warns on when it expires.

## What NOT to do

- **Don't push directly to `main`.** Branch protection blocks it. Use a feature branch + MR.
- **Don't create a `release/*` branch.** Promotion is a manifest MR, not a branch cut.
- **Don't rebase because `main` moved.** The merge train does that. Rebase only for a real conflict.
- **Don't rebase `main`**, and don't rewrite any commit a `v/` tag points at.
- **Don't move or delete a `v/` tag.** It is both the rollback target and the audit record.
- **Don't run `databricks bundle deploy` against staging or prod by hand.** `tools/scripts/reconcile.py` is the only thing that touches them — that's what makes the manifest true rather than aspirational.

## Pushing from a Databricks Git Folder

Same model. The Git Folder commits and pushes to the same repo, and CI runs
server-side regardless of origin. Pre-commit hooks don't fire from the Databricks
side — run `notebooks/_pre_push_check.py` first. See
`docs/runbooks/databricks-git-folder-workflow.md`.

## The view from each role

| Role | Owns | Approves | Never does |
|---|---|---|---|
| Data engineer | Feature branch, sandbox schema, tests, contracts | — | Deploys to staging or prod |
| CODEOWNER | Code quality in their folder | MRs into `main` | Approves their own MR |
| Release approver | `release/staging/`, `release/prod/` | Promotions, pauses, retires | Approves a pipeline they triggered |
| Platform team | `platform/`, `infra/`, the reconciler | Infra and CI changes | Edits a team's project code |

## See also

- `release-process.md` — the promotion procedure
- `gitlab-setup-release-model.md` — the GitLab configuration that enforces all of this
- `docs/superpowers/specs/2026-09-01-modular-release-model-design.md` — the full design and its rationale
- `bootstrap-ci-and-audit.md` — CI auth + audit bucket setup
- `codeowners-maintenance.md` — when CODEOWNERS changes
- `databricks-git-folder-workflow.md` — pushing from inside Databricks
