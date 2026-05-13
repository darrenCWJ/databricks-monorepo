# apps/ — Databricks Asset Bundles

## What goes here
One subdirectory per deploy unit (pipeline, job, or streaming app).
Each app is a Databricks Asset Bundle (DAB) with its own `bundle.yml`.

## Structure per app
```
apps/<team>-<verb>-<noun>/
├── AGENTS.md          # What this app does, inputs, outputs, SLA
├── bundle.yml         # DAB definition (jobs, clusters, schedules)
├── pyproject.toml     # Python deps (or build.sbt for Scala)
├── notebooks/         # Thin notebook shims (logic lives in src/)
├── src/<package>/     # Business logic (unit-testable)
└── tests/             # pytest (Python) or ScalaTest (Scala)
```

## Rules
1. One app = one team's concern. Never edit across app boundaries in one PR.
2. Business logic goes in `src/`, not notebooks. Notebooks are thin shims.
3. Every app must have `AGENTS.md` (≤80 lines) describing purpose, I/O, SLA.
4. Tests must pass locally before opening an MR (`just test apps/<name>`).
5. No secrets in code. Use Databricks secret scopes via `${secrets.scope.key}`.

## Creating a new app
```bash
just new-app <name> --kind python|scala|streaming
```

## Deploying
```bash
just bundle-validate apps/<name>
just bundle-deploy apps/<name> -t dev
just bundle-run apps/<name> <task_key> -t dev
```
