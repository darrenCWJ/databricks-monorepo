# Runbook: migrate the monorepo to Pants Build

For the future platform team that hits one of the architectural triggers
documented in `docs/adr/0001-monorepo-architecture.md`. Don't run this
unless you have to — the current setup costs ~10% of what Pants would.

## When to migrate

Run this only when one of the four triggers fires:

| Trigger | Threshold |
|---|---|
| Engineering headcount | ≥ 75 |
| CI feedback time (after path filters) | > 15 min median |
| Cross-language change-impact pain | Daily false negatives or false positives from `affected.py` |
| Audit / regulatory pressure for fully reproducible builds | E.g., FedRAMP-style hermetic action graphs |

If none of these are true, stay on uv + Makefile + `affected.py`.

## What survives the migration

About 95% of the repository:

- Folder taxonomy (`apps/`, `libs/`, `dbt/`, `infra/`, `tools/`, `docs/`)
- All `AGENTS.md` content except the "command surface" section
- `CODEOWNERS`
- All `bundle.yml` files (DABs are deploy units, not build units)
- All dbt projects + mesh + cross-project refs + `schema.yml`
- Compliance scripts (`check_pii_contract.py`, `audit_log.py`, etc.)
- All Python and Scala source
- Lakebase sync rules
- Service principals, audit bucket, IM8 hardening

## What changes

| Today | After Pants |
|---|---|
| `pyproject.toml` `[tool.uv.workspace]` | `pants.toml` + `BUILD` files per package |
| `uv.lock` | `3rdparty/python/default.lock` (Pants resolves) — or keep `uv.lock` for IDEs |
| `Makefile` recipes | Same recipes, but invoke `pants <goal>` |
| `tools/scripts/affected.py` | Delete — `pants --changed-since=origin/main` replaces it |
| `build.sbt` per Scala app | Pants JVM `BUILD` targets |
| `.gitlab-ci.yml` | Rewritten around `pants test ::`, `pants lint ::`, `pants package ::` |
| Pre-commit hooks | Replace `affected.py`-driven ones with `pants --changed-since=HEAD` |
| Internal Artifactory in `pyproject.toml` | `[python-repos]` in `pants.toml` |

## Phased migration plan (~6-10 weeks)

### Phase 0 — preparation (week -1)

- Open a tracking issue. Tag `@cdo/platform-team` + each team lead.
- Spin up a remote-cache backend in advance (BuildBuddy, S3-backed Pants
  cache, or a Pants Cache instance). Provisioning takes ≥ 1 week.
- Add a temporary CI job that runs Pants alongside existing CI without
  blocking. Compare outputs.

### Phase 1 — Pants scaffold on libs/ (weeks 1-2)

Smallest blast radius, no production deploy paths.

```bash
# At repo root
curl -L -O https://github.com/pantsbuild/scie-pants/releases/latest/download/scie-pants-linux-x86_64
chmod +x scie-pants-linux-x86_64
mv scie-pants-linux-x86_64 ./pants

# Initial pants.toml — minimal
cat > pants.toml << 'POOF'
[GLOBAL]
pants_version = "2.20.0"
backend_packages = [
  "pants.backend.python",
  "pants.backend.python.lint.ruff",
  "pants.backend.python.typecheck.mypy",
]
[python]
interpreter_constraints = ["CPython==3.11.*"]
[python-repos]
indexes = ["https://artifactory.cdo.gov.sg/api/pypi/pypi-prod/simple"]
POOF

# Auto-generate BUILD files
./pants tailor ::

# Test the libs
./pants test libs::
```

Goal: green test run for every `libs/<name>/`.

### Phase 2 — apps/ Python (weeks 3-4)

Per-team rollout. Recommend one team per week to keep MR review load
sane.

```bash
./pants tailor apps/finance-*::
./pants test apps/finance-*::
./pants package apps/finance-*::    # builds the wheel
```

Once a team's apps pass: update their `bundle.yml` to reference the
Pants-built wheel path:

```diff
-     - whl: ../../dist/customer360_etl-*.whl
+     - whl: ../../dist/pants/apps.customer360-etl.customer360_etl-*.whl
```

### Phase 3 — Scala (weeks 5-6)

Largest single chunk. Enable JVM backend in pants.toml:

```toml
backend_packages = [
  ...,
  "pants.backend.experimental.scala",
]
[scala]
version_for_resolve = { jvm-default = "2.12.18" }
```

For each Scala app:

```bash
./pants tailor apps/fraud-streaming::
./pants test apps/fraud-streaming::
./pants package apps/fraud-streaming::deploy_jar
```

The generated `BUILD` files declare `scala_sources`, `scalatest_tests`,
and a `deploy_jar` target that produces the fat JAR (replaces sbt
assembly). Tune `[jvm]` settings in `pants.toml` for heap, parallelism.

### Phase 4 — CI rewrite (week 7)

Replace `.gitlab-ci.yml` with a Pants-aware version. Key snippet:

```yaml
test:
  stage: test
  image: python:3.11-slim
  script:
    - pip install --quiet uv pants
    - pants --changed-since=origin/main test
    - pants --changed-since=origin/main lint
    - pants --changed-since=origin/main check
  cache:
    paths: [".pants.d", "~/.cache/pants"]

bundle-validate:
  stage: bundle
  script:
    - pants --changed-since=origin/main package ::
    - for b in $(find apps -name bundle.yml -exec dirname {} \;); do
        (cd "$b" && databricks bundle validate); done
```

Delete `tools/scripts/affected.py` and its pre-commit hook.

### Phase 5 — Makefile pass-through (week 7)

The `Makefile` becomes a thin wrapper so engineers don't have to learn
two CLIs in week 1:

```make
test PATH=".":
    ./pants test {{PATH}}::

lint PATH=".":
    ./pants lint {{PATH}}::

bundle-validate PATH:
    cd {{PATH}} && databricks bundle validate
```

(Could also just retire the Makefile — engineers learn `pants` direct.
Team preference.)

### Phase 6 — AGENTS.md cascade (week 8)

Find/replace `make <verb>` with `pants <verb>` across every `AGENTS.md`
in the repo:

```bash
git grep -l 'make test\|make lint\|make bundle-validate' \
  | xargs sed -i '' 's/make test/pants test/g; s/make lint/pants lint/g'
```

Open one MR per major area: root AGENTS.md, dbt/AGENTS.md, apps,
libs, docs/. Review with each team lead.

### Phase 7 — retire transitional infrastructure (week 9)

- Turn off the parallel-run CI job from Phase 0
- Delete `uv.lock` if migrating fully to Pants resolves
- Delete `pyproject.toml` `[tool.uv.workspace]` section
- Delete every `apps/*/pyproject.toml` `[build-system]` block (Pants
  produces the wheels now)

### Phase 8 — remote cache (week 10)

Wire the cache backend you provisioned in Phase 0:

```toml
[GLOBAL]
remote_cache_read = true
remote_cache_write = true
remote_store_address = "grpc://buildbuddy.cdo.internal:1985"
remote_store_headers = {"x-buildbuddy-api-key": "%(env.BUILDBUDDY_API_KEY)s"}
```

This is when builds get measurably faster. Without remote cache, Pants
roughly matches the current `affected.py` performance — the wins come
from the cache.

## What does NOT need to change

- `dbt/` — Pants ignores it. Continue invoking `dbt build` as a shell
  task or via a Pants `shell_command` target.
- `bundle.yml` — DABs are deploy artefacts. Pants produces the wheels and
  JARs; `databricks bundle deploy` consumes them.
- `tools/scripts/where_is.py`, `check_pii_contract.py`,
  `check_ownership_sync.py`, `lint_agents_md.py`, `audit_log.py`,
  `dump_access.py`, `diff_outputs.py`, `import_job.py` — all survive
  unchanged.
- Lakebase sync rules, IM8 compliance scaffolding, all docs/compliance/
  content.
- `CODEOWNERS`, MR template, GitLab Protected Environments.

## Compatibility test gate

Before turning off the legacy CI, every MR in flight for 2 weeks should
pass both pipelines. Watch for:

- Test discovery differences (Pants finds tests by `:tests` target; uv
  finds them by `pytest` discovery). Reconcile.
- Wheel naming differences. Update `bundle.yml` library references.
- Pre-commit timing differences. Pants's `lint --changed-since=HEAD` is
  typically faster but reports failures with slightly different formatting.

## Rollback

If Phase 1-4 reveals a blocker, you can roll back at any point because
the legacy CI is still running in parallel. Revert the Pants-related
files, keep everything else. The only "burnt" effort is the BUILD files
and pants.toml — they can sit dormant.

After Phase 7, rollback is expensive (would require regenerating uv
workspace metadata). Don't proceed past Phase 7 without 2 weeks of clean
runs in Phase 6.

## Agent impact

Negligible. `AGENTS.md` is the contract between the agent and the repo;
the agent reads "use `pants test PATH`" the same way it reads
"use `make test P=PATH`" today. Folder structure, classification contracts,
cross-project ref pattern, `where_is.py` — all unchanged.

The single MR that updates every `AGENTS.md`'s command surface is the
moment the agent's mental model shifts. After that day, agents work
exactly as they did before.

## See also

- `docs/adr/0001-monorepo-architecture.md` — the original architecture
  decision listing the four triggers.
- `agent-friendly-monorepo.md` (in the report) §14 "When to revisit this
  decision."
