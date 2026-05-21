# Data Engineer — 5-day onboarding

You will build and ship Databricks Asset Bundles (DABs) for your team.

## What you'll touch in this repo
- `apps/<team>-*/` — your team's deploy units
- `apps/<team>-*/src/` — testable Python (the home of your business logic)
- `apps/<team>-*/tests/` — pytest, unit + integration
- `apps/<team>-*/bundle.yml` — the DAB definition (jobs, schedules, clusters)
- `libs/<team>-common/` — your team's shared code
- `libs/common-*` — platform-wide libs (read-only; changes go through @cdo/platform-team)

## Day 1 — tools & first clone
- Install `uv`, `just`, `databricks` CLI (see root README §Tooling install)
- `git clone` the repo
- `make setup` — installs all deps, sets up pre-commit
- Read root `AGENTS.md` and at least one `apps/<team>-*/AGENTS.md`

## Day 2 — get familiar
- Pick an existing app in your team's neighbourhood; read its AGENTS.md
- `make test P=apps/<that-app>` — confirm tests pass on your laptop
- `databricks auth login -p dev` — confirm you can reach the dev workspace

## Day 3 — pair on a small bug fix
- Find an issue tagged `good-first-task` in your team's neighbourhood
- Open the MR; let CI run; iterate
- Get your first review from a team-mate

## Day 4 — independent change
- Open an MR for a real but bounded change in an existing app
- Watch CI: `affected.py` should scope the run to your app only
- 3–5 minutes from push to green

## Day 5 — full lifecycle
- `make bundle-deploy P=apps/<that-app> T=dev`
- Verify the audit-log entry lands in `cdo-soc2-audit-dev/`
- You've now done the full "scaffold → test → deploy → audit" loop

## Rules to internalise
1. Never cross `apps/<team-X>` and `apps/<team-Y>` in one MR.
2. Logic lives in `src/`. Notebooks stay thin (widget + import + call).
3. Library API changes ship in a dedicated MR; consumers update separately.
4. New deploy unit = new directory under `apps/` with `bundle.yml` + `AGENTS.md`.
