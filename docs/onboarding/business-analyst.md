# Business Analyst — 5-day onboarding

You will use the platform to answer questions, build dashboards, and request
new data products. You do NOT need to clone the repo.

## What you'll touch
- Databricks SQL editor (in the workspace UI)
- AI/BI dashboards (in the Databricks workspace)
- Unity Catalog browser (to find tables you have access to)
- This repo — read-only via GitLab, mostly the `dbt/<team>/models/marts/schema.yml`
  files (to understand what columns mean and how they're classified)

## Day 1 — access
- Get a Databricks workspace account (request via service desk)
- Confirm membership of `@cdo/<team>` Databricks group
- If you need to read PII columns in the clear, request membership of
  `cdo_pii_readers_<env>` — this requires HR/Security clearance

## Day 2 — explore the catalogue
- Open Databricks → Catalog Explorer
- Browse `cdo_<env>.<team>.*` — these are your team's published marts
- Click any column: see its tags (pii, classification, sensitivity)
- Read `dbt/<team>/AGENTS.md` in GitLab for the team's naming conventions

## Day 3 — first SQL query
- Open Databricks SQL editor
- Write a query against a published mart in your team's schema
- Save it. Share with a teammate for review

## Day 4 — first dashboard
- Open AI/BI dashboards
- Build a small dashboard from your saved query
- Configure refresh schedule + audience

## Day 5 — publish and capture
- Share dashboard with stakeholders
- Capture consumers in `docs/usage.md` (open a PR to the platform repo
  documenting who depends on this dashboard, so the upstream team knows
  what they'll break if they change a column)

## Need new data?
- Open an issue on the GitLab repo against the relevant team's neighbourhood
  (e.g., `apps/finance-*` for Finance data)
- Describe the question, not the schema — the team will translate
