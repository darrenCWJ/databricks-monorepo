# Runbook: setting up GitLab for the release model

Everything in `branching-strategy.md` and `release-process.md` depends on GitLab
being configured a particular way. This runbook is that configuration: what to
set, why, and how to verify it took.

Do it once, in the order below. Steps 1–4 are safe at any time. Step 5 changes
who can deploy, so announce it first.

> Platform team owns this document. Every setting here is a governance control —
> changing one is an MR-sized decision, not a click.

## Step 0 — confirm the tier

Several controls need GitLab **Premium or Ultimate**. Check
**Admin → Subscription** (self-managed) or **Group → Settings → Billing**.

| Feature we depend on | Tier | If unavailable |
|---|---|---|
| Merge trains | Premium | Fall back to "merge when pipeline succeeds" + merged-results pipelines. You lose automatic rebasing; engineers rebase by hand. |
| Protected environments with required approvals | Premium | Build the prod gate as a second MR approval on `release/prod/` instead. Weaker — the approver is not provably different from the triggerer. |
| Push rules (branch/commit regex, tag-delete denial) | Premium | Enforce in CI instead — a `lint` job that fails on a bad branch name. Catches it later, but catches it. |
| Fast-forward merge **with** merge trains | Premium, GitLab 16.4+ | On self-managed also check the `fast_forward_merge_trains_support` feature flag. |
| Compliance frameworks / required pipelines | Ultimate | Optional. Nice-to-have, not load-bearing. |

**If we are on Free, stop and escalate.** The SOC2 segregation-of-duties control
on production deployment cannot be enforced by the tool on Free, and would have
to become a documented manual control — which auditors treat very differently.

## Step 1 — merge request settings

**Settings → Merge requests**

| Setting | Value | Why |
|---|---|---|
| Merge method | **Fast-forward merge** | Linear `main`. Makes `git diff BASE...HEAD` in `affected.py` and "what changed between two prod refs" unambiguous. |
| Squash commits when merging | **Require** | One MR = one commit on `main` = one tag = one rollback unit. Rollback granularity equals review granularity. |
| Merge trains | **Enable** | The train rebases for you. See Step 8. |
| Pipelines must succeed | **On** | |
| Skipped pipelines are considered successful | **Off** ⚠️ | We run affected-only CI. Left on, a skipped job counts as green and a red MR merges. |
| All threads must be resolved | **On** | |
| Delete source branch by default | **On** | Keeps the branch list at roughly the number of engineers mid-task. |
| Enable "Merge requests approvals" | **On** | |

## Step 2 — push rules

**Settings → Repository → Push rules.** This is where branch naming stops being
a convention people remember and becomes something the server refuses.

| Rule | Value |
|---|---|
| Branch name | `^(main\|(feature\|hotfix)\/[a-z0-9][a-z0-9-]*\|recovery\/v-[a-z0-9.-]+)$` |
| Commit message | `^(feat\|fix\|docs\|refactor\|test\|chore\|perf\|ci)(\(.+\))?: .+` |
| Prevent pushing secrets | **On** |
| Deny deleting a tag | **On** ⚠️ |
| Check whether author is a GitLab user | **On** |
| Reject unsigned commits | **On** if the team has GPG set up |

**"Deny deleting a tag" is the important one.** `v/` tags are simultaneously our
rollback targets and our audit evidence. A deleted tag destroys both.

Regexes use RE2 and are capped at 511 characters.

The branch-name regex is exactly the branch table in `branching-strategy.md`. If
someone tries `feat/thing` or `release/2026-09-01`, the push is rejected at the
pre-receive hook with a clear message — not three days later in review.

## Step 3 — protected branches and tags

**Settings → Repository → Protected branches**

| Branch | Allowed to push | Allowed to merge | Force push | Code owner approval |
|---|---|---|---|---|
| `main` | **No one** | Maintainers | Off | **Required** |

"No one" includes maintainers and owners. There is no legitimate direct push to
`main` — if there were, CODEOWNERS is bypassed and CI never runs.

**Settings → Repository → Protected tags**

| Tag pattern | Allowed to create |
|---|---|
| `v/*` | Maintainers **and the CI job token only** |

Tags are created by the `tag-release` CI job. No human should ever create one —
a hand-made tag is a claim that something passed CI when it may not have.

## Step 4 — approval rules

**Settings → Merge requests → Merge request approvals**

| Setting | Value |
|---|---|
| Approvals required | 1 |
| Prevent approval by the author | **On** |
| Prevent approvals by users who add commits | **On** |
| Prevent editing approval rules in merge requests | **On** |
| Remove all approvals when commits are added | **On** |
| Require CODEOWNER approval on protected branches | **On** |

The last two together are what stop the "approve, then push one more commit"
pattern that quietly defeats review.

## Step 5 — groups and protected environments

Create two groups **now**, even though they are the same two people today.
Adding a third person later should be a membership change, not a redesign.

- `@cdo-code-owners` — reviews code
- `@cdo-release-approvers` — authorises deployments

**Settings → CI/CD → Protected environments**

| Environment | Allowed to deploy | Required approvals |
|---|---|---|
| `dev` | CI service account | 0 — fully automatic |
| `staging` | `@cdo-release-approvers` | 0 — manual trigger only |
| `production` | `@cdo-release-approvers` | **1** |

With one required approval, GitLab will not let the person who triggered the
deployment pipeline approve it. **That is the SOC2 segregation-of-duties control,
enforced by the tool rather than remembered by a person** — the single most
valuable thing in this runbook.

Two-person approver groups mean production freezes when both are away. Agree a
break-glass procedure and write it into `docs/runbooks/` before you need it.

## Step 6 — CODEOWNERS

Route each environment separately. **Teams manage their own dev.** The CODEOWNERS
gate is the merge into `main` — it is not a second gate on a team's own sandbox
environment, so a dev entry routes to the same people who own the project's code:

```
# Release control plane — dev is owned by the team that owns the project
/release/dev/finance-*        @cdo-finance-leads
/release/dev/supplier-*       @cdo-supplier-leads
/release/staging/             @cdo-release-approvers
/release/prod/                @cdo-release-approvers

# Platform
/platform/                    @cdo-platform-team
/infra/                       @cdo-platform-team @cdo-data-governance
/.gitlab-ci.yml               @cdo-platform-team
/tools/scripts/reconcile.py   @cdo-platform-team

# Projects — team wildcards, so a new project needs no new line
/projects/finance-*/          @cdo-finance-leads
/projects/supplier-*/         @cdo-supplier-leads
```

The wildcards matter for the reason in Step 8: a file every new project has to
append to is a file two teams conflict on.

## Step 7 — CI variables

**Settings → CI/CD → Variables.** All **masked** and **protected**.

| Variable | Scope | Notes |
|---|---|---|
| `DATABRICKS_HOST_DEV` / `_STAGING` / `_PROD` | per environment | |
| `DATABRICKS_CLIENT_ID` / `_SECRET` | per environment | Distinct service principal per environment. Never share one. |
| `AUDIT_BUCKET` | all | WORM S3 bucket for `audit_log.py` |
| `RELEASE_TAG_TOKEN` | protected only | Project access token, `write_repository`, used only by `tag-release` |

The prod credentials must be **protected** variables, so they are unavailable to
pipelines on unprotected branches. Otherwise any feature branch can read them.

## Step 8 — how order is maintained

This is the part people ask about most: *many engineers, one `main` — how does it
not become chaos?*

### The merge train is the ordering mechanism

Put an MR on the train and it joins a FIFO queue. GitLab then runs **parallel**
pipelines: each MR is tested against `main` plus every change queued ahead of it.
An MR merges only when its own pipeline passes **and** everything ahead of it has
merged.

This is speculative execution — the same design as Uber's SubmitQueue, which took
their monorepo mainline from green 52% of the time to green permanently at
thousands of commits a day. Because the pipelines run in parallel rather than
strictly one after another, throughput is not capped at one MR per pipeline
duration.

### What happens when something fails

A failed train pipeline drops that MR from the train, and GitLab immediately
starts fresh pipelines for everything queued behind it. You cannot retry the
failed pipeline directly — its merged result is now out of date. Fix and re-add
to the train.

**Consequence worth acting on:** a flaky job drops people from the train and
makes everyone behind them wait for a re-run. Put `retry:` on anything network-
dependent so intermittent failures are absorbed before they cost the queue:

```yaml
bundle-validate:
  retry:
    max: 2
    when: [runner_system_failure, stuck_or_timeout_failure, api_failure]
```

### Nobody rebases because `main` moved

The train does that. Rebase by hand only when git reports a genuine textual
conflict. If people are hand-rebasing for staleness, something in Step 1 is wrong.

### Dependent changes

If MR B genuinely needs MR A, the train does not know that. Either merge A first
and then open B, or combine them. Do not queue both and hope — B will be tested
against a `main` that contains A, pass, and then merge in an order that is only
correct by luck.

**Manifest promotions have no such constraint.** Two teams promoting at the same
time edit different files under `release/prod/`, so they cannot conflict and their
order does not matter. The one real ordering constraint across projects is data:
if project A's output feeds project B, promoting A can break B. That is what the
`contract-gate` job exists to catch, and it is the reason it runs against every
project currently `active` in prod rather than just the one being promoted.

### Keep merge requests small

The DORA research puts short-lived at **under one day**, and finds elite
performers 2.3× more likely to work that way. Uber found large diffs stall a
merge queue badly enough to need special handling.

So: a branch open more than a couple of days should be split. This is a norm, not
a setting — but it is the norm that makes everything above cheap.

## Step 9 — scripted setup

Configure by API rather than by clicking, so the setup is reproducible and the
change itself is auditable. Run once, keep the script in `tools/scripts/`.

```bash
# Requires: a maintainer token in $GL_TOKEN, project id in $PROJECT
GL="https://gitlab.example.com/api/v4/projects/$PROJECT"
H="PRIVATE-TOKEN: $GL_TOKEN"

# Push rules — branch naming, conventional commits, tag protection
curl -sS --request PUT --header "$H" --url "$GL/push_rule" \
  --data-urlencode 'branch_name_regex=^(main|(feature|hotfix)\/[a-z0-9][a-z0-9-]*|recovery\/v-[a-z0-9.-]+)$' \
  --data-urlencode 'commit_message_regex=^(feat|fix|docs|refactor|test|chore|perf|ci)(\(.+\))?: .+' \
  --data "deny_delete_tag=true" \
  --data "prevent_secrets=true" \
  --data "member_check=true"

# Protected tags — only maintainers and CI may create v/*
curl -sS --request POST --header "$H" --url "$GL/protected_tags" \
  --data "name=v/*" --data "create_access_level=40"

# Approval settings
curl -sS --request POST --header "$H" --url "$GL/approvals" \
  --data "merge_requests_author_approval=false" \
  --data "merge_requests_disable_committers_approval=true" \
  --data "reset_approvals_on_push=true" \
  --data "disable_overriding_approvers_per_merge_request=true"
```

Endpoint shapes vary a little between GitLab versions — check each against your
instance's API docs before running, and run against a scratch project first.
Protected branches (`/protected_branches`), protected environments
(`/protected_environments`) and merge-method settings (`PUT /projects/:id`) follow
the same pattern.

## Step 10 — verify it took

Do all of these. Each should **fail**.

| Try to | Expected |
|---|---|
| `git push origin main` | Rejected — protected branch |
| `git push origin feat/thing` | Rejected — push rule, branch name |
| `git commit -m "stuff"` then push | Rejected — push rule, commit message |
| `git tag -d v/x/2026-01-01.1 && git push --delete origin …` | Rejected — deny delete tag |
| Approve your own MR | Button unavailable |
| Approve, push a commit, merge | Approval reset, merge blocked |
| Trigger `reconcile-prod` and approve it yourself | Approval refused — different approver required |
| Merge an MR whose only jobs were skipped | Blocked, if Step 1 is right |

Record the results with dates in `reviews/YYYY-MM-DD/gitlab-controls.md`. That
folder is deliberately committed — it is audit evidence.

## Step 11 — keeping it orderly over time

| Cadence | Do |
|---|---|
| Nightly | `reconcile.py --check` — drift between the manifest and each workspace, including anything changed by hand in the Databricks UI |
| Nightly | `check-environments` — expired `review_by` on any paused project |
| Weekly | Sweep branches with no commit in 14 days; ask the owner to split or close |
| Monthly | Review the `paused` list. A pause older than its `review_by` is either a decision nobody made or a project that should be `retired`. |
| Quarterly | `make dump-access` and walk the four grant layers — see `quarterly-access-review.md` |
| Quarterly | Re-run the Step 10 verification table. Settings drift when people debug things. |

The nightly drift check is the one that matters most. Without it the manifest is
a claim about production; with it, it is a verified fact.

## Governance control map

What an auditor will ask, and what to show them.

| Question | Control | Evidence |
|---|---|---|
| Can anyone change prod without review? | Protected branch, push: no one | Branch protection settings |
| Is every change reviewed by someone else? | CODEOWNERS + prevent-author-approval | MR approval records |
| Is the deployer different from the approver? | Protected environment, 1 required approval | Deployment approval records |
| Is every change tied to a ticket? | MR template + `commit_message_regex` | MR descriptions |
| What ran in prod on a given date? | Release manifest | `git log -p release/prod/` |
| Can that record be altered after the fact? | Protected branch + deny-delete-tag | Push rules; tags are immutable |
| Who can see Restricted columns? | UC masks + row filters | `make dump-access` output |
| Did anything change outside the process? | Nightly drift check | `reconcile.py --check` output |

## See also

- `branching-strategy.md` — branches, merge trains, hotfixes, rollback
- `release-process.md` — the promotion procedure
- `bootstrap-ci-and-audit.md` — CI auth and the audit bucket
- `codeowners-maintenance.md` — when CODEOWNERS changes
- `docs/superpowers/specs/2026-09-01-modular-release-model-design.md` — the design and its open decisions

### Reference

- Ananthanarayanan et al., *Keeping Master Green at Scale*, EuroSys 2019 — the merge-queue design GitLab merge trains implement
- DORA, *Trunk-based development* — the evidence for short-lived branches
