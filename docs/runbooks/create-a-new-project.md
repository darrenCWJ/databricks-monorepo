# Runbook: create a new project

Half a day end-to-end, excluding business logic. Use this for greenfield
projects. For pulling in an existing repo, see `migrate-a-repo.md`.

## Step 0 — pick a pattern

| Pattern | Project type | Where |
|---|---|---|
| A | Batch (App) | `apps/<team>-<verb>-<noun>/` |
| B | Streaming (App) | `apps/<team>-streaming-<noun>/` |
| C | ML training (App) | `apps/<team>-ml-<noun>/` |
| D | Low-latency reads (App + Lakebase publish) | `apps/<name>/` |
| E | Operational capture (App + Lakebase capture) | `apps/<name>/` |
| F | Bidirectional (App + Lakebase) | `apps/<name>/` |
| L | Library | `libs/<team>-common/` |

See the interactive walkthrough page for what each pattern produces.

## Step 1 — pick a name + confirm the owner

Naming: `apps/<team>-<verb>-<noun>` — lowercase, hyphenated.

Confirm with the team lead before scaffolding. If a similar name
exists, talk to that team first.

## Step 2 — scaffold

```bash
just new-app finance-payment-recon --kind python    # or --kind scala
```

Library:

```bash
just new-lib finance-common
```

The scaffold generates `bundle.yml`, `src/<package>/`, `tests/`,
`notebooks/`, and a stub `AGENTS.md`.

## Step 3 — register everywhere

Three root files must know about the new project:

- `pyproject.toml` — add to `[tool.uv.workspace] members` (Python only).
- `CODEOWNERS` — verify your team's wildcard matches, or add a new line.
- `databricks.yml` — add the include for `apps/<name>/bundle.yml`.
- `docs/data-architecture.md` — add a row to Tables 1, 2, 3.

Then sync:

```bash
just setup
```

## Step 4 — fill in AGENTS.md

The stub asks the right questions; you answer them: inputs, outputs,
SLA, classification, owners. Keep it under 80 lines.

See `apps/AGENTS.md` for the rules every app must follow — don't
repeat those.

## Step 5 — write tests first

Pure transforms in `src/<package>/transforms.py`, unit tests in
`tests/unit/`. Run:

```bash
just test apps/<name>
```

No business logic without tests. See `best-practices/testing.md`.

## Step 6 — configure deployment

Edit `apps/<name>/bundle.yml`:

- Job name + schedule (or `continuous: {}` for streaming).
- Cluster via `${var.cluster_node_type_id}`.
- `run_as: { service_principal_name: ${var.staging_sp} }` for non-dev.
- `on_failure` email notifications.

If pattern D/E/F: add a `synced_database_tables` resource.

## Step 7 — pre-flight check locally

```bash
just lint apps/<name>
just test apps/<name>
just bundle-validate apps/<name>
```

All three must pass.

## Step 8 — open the MR

Template asks for: change ticket ID, risk + rollback notes,
data-classification touchpoints. CODEOWNER approval required, NOT
from the author.

CI runs affected-only: lint, test, bundle-validate, security stage.
3–5 minutes typically.

## Step 9 — first deploy to dev

Merge to `main` auto-deploys to dev. Trigger the job manually first
time:

```bash
just bundle-run apps/<name> <task_key> -t dev
```

## Step 10 — ship to staging and prod

1. Release manager cuts `release/YYYY-MM-DD` from `main`.
2. Trigger `deploy-staging` manually.
3. Bake ≥ 24h, run smoke tests.
4. Trigger `deploy-prod` manually (different approver — SOC2).

See `release-process.md`.

## Step 11 — capture an ADR (if significant)

Required when: cross-team data flow, new pattern, Restricted data
touched, non-obvious architectural choice.

```bash
cp docs/adr/0001-monorepo-architecture.md docs/adr/00NN-<your-project>.md
```

Edit it: what the pipeline does, alternatives considered, residual
risks, owner.

## Checklist

- [ ] Picked pattern (A–F or library)
- [ ] `apps/<team>-<verb>-<noun>` name confirmed with lead
- [ ] Scaffold ran: `just new-app …`
- [ ] Added to `pyproject.toml` workspace members (Python)
- [ ] Added to `CODEOWNERS` (or wildcard already matches)
- [ ] Added include in `databricks.yml`
- [ ] Added rows to `docs/data-architecture.md`
- [ ] `AGENTS.md` filled in (≤ 80 lines)
- [ ] At least one unit test written
- [ ] All Delta-write columns have classification metadata
- [ ] `just lint` / `just test` / `just bundle-validate` all pass
- [ ] MR opened with change-ticket ID
- [ ] CI green
- [ ] CODEOWNER approved (not the author)
- [ ] Merged to `main`, deployed to dev
- [ ] Smoke-tested dev
- [ ] ADR written if significant
