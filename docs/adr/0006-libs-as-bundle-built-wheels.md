# ADR-0006: Shared libraries ship as bundle-built wheels, not a shared workspace path

- **Status**: Accepted
- **Date**: 2026-09-01
- **Deciders**: Platform team
- **Amends**: ADR-0003 (the `src/` layout stands; the `sys.path.append` consumption pattern does not)

## Context

`ADR-0003` standardised the `src/` layout for `libs/` and prescribed how notebooks
consume them:

```python
import sys
sys.path.append("/Workspace/Repos/shared/mono-dev/libs/de_toolbox/src")
from de_toolbox.pipeline.copper import create_copper_table
```

One path. One copy per workspace. Whatever that Git Folder is synced to is what
every job in that workspace imports.

That was fine while the release model promoted the whole repo at once — the
workspace was always at one commit, so a single lib copy was the correct
representation of reality.

It stopped being fine when we moved to per-project promotion
(`docs/superpowers/specs/2026-09-01-modular-release-model-design.md`). Under that
model each project pins its own git ref, and the manifest can legitimately hold
Finance at `2026-08-17.1` while Supplier sits at `2026-07-30.2`. But both import
`de_toolbox` from the same workspace path, so:

- **Promoting Finance silently changes Supplier's library code.** Supplier's
  bundle is not deployed, not tested, and not mentioned in the MR. Its behaviour
  changes anyway.
- **Rollback is a lie.** Pointing Finance's ref at an older tag restores its
  project code and leaves the library at whatever the workspace was last synced to.
- **`make affected` reports a blast radius the deployment model cannot honour.**
  It correctly names every consumer of a changed lib — but there is no mechanism
  to give those consumers a different version.

The lib path was the single remaining thing making "independent promotion" untrue.

Two facts shaped the decision:

1. **Artifactory is blocked.** CI installs tooling via `uvx` from public PyPI
   specifically to avoid it. There is no internal registry to publish to today.
2. **`projects/` is empty.** No project has been built against the old pattern
   yet, so the migration cost is close to zero now and grows with every project
   added.

## Decision

**Shared libraries are built as wheels by the Databricks Asset Bundle that
consumes them, from the source at that bundle's pinned git ref, and installed
onto the job's compute as a task library.**

Each project's `databricks.yml` declares the libs it uses:

```yaml
artifacts:
  de_toolbox:
    type: whl
    path: ../../../libs/de_toolbox
    build: uv build --wheel

resources:
  jobs:
    customer360_etl:
      tasks:
        - task_key: transform
          notebook_task:
            notebook_path: ./notebooks/transform.py
          libraries:
            - whl: ../../../libs/de_toolbox/dist/*.whl
```

Notebooks then import normally, with no path manipulation:

```python
from de_toolbox.pipeline.copper import create_copper_table
```

`databricks bundle deploy` runs the build command and uploads the resulting wheel
under **that bundle's own root path, for that target**. Finance's `de_toolbox` and
Supplier's `de_toolbox` are separate uploaded artifacts built from separate
commits. Neither can move the other.

Which libs a project declares is not a new source of truth: every project already
lists its lib dependencies in `pyproject.toml`, and `check_lib_deps.py` already
fails CI when an import is undeclared. The `artifacts` block is generated from
that same declaration.

### Libraries are not independently versioned

There is no `de-toolbox==0.4.2` pin. **The project's git ref is the library
version.** One ref names one consistent set of project code and library code.

This is the standard monorepo position — a single commit describes the whole
world — and it is what makes a lib change and its consumer updates possible in
one atomic MR. The `version` field in `libs/*/pyproject.toml` stays as
human-facing metadata and as preparation for a registry we do not yet have.

## Consequences

### What this buys

- **Independent promotion becomes true rather than nearly true.** Every claim in
  the release model now holds for projects that use shared libraries — which is
  intended to be all of them.
- **Rollback is complete.** An older ref restores project code *and* library code
  together, because they were always one artifact.
- **No registry needed.** Unblocks the whole design without waiting on Artifactory.
- **`make affected` becomes actionable.** The blast radius it reports can now be
  acted on: promote the affected consumers, or don't, per project.

### What it costs, and what to watch

- **Two projects can run different `de_toolbox` builds in production
  simultaneously.** This is not a bug — it is precisely what independent
  promotion means — but it has a consequence: **libraries must stay backward
  compatible for at least `rollback_depth_days`.** A breaking change to a lib is
  a coordinated, multi-project change, and belongs in a dedicated MR per the
  existing rule in `AGENTS.md`.
- **Deploy is slower.** Each deploy builds and uploads a wheel. Seconds, not
  minutes, but it is not free.
- **"Which library version is Finance running?"** is answered by Finance's pinned
  ref, and is verifiable from the `cdo_release_ref` / `cdo_git_sha` tags stamped
  on every deployed resource. Optionally, DAB supports dynamic wheel versioning so
  the installed distribution itself carries the commit — worth adding if reading
  `pip list` on a cluster proves to be the common diagnostic path.
- **Non-job compute needs its own answer.** Task `libraries` covers jobs and DLT
  pipelines. **Databricks Apps and serverless do not use it** — they resolve
  dependencies from `requirements.txt`. Those project types must carry the wheel
  another way; that is not solved here and must be settled before the first `app`
  or `api` project ships.

### Interactive development

Removing `sys.path.append` removes the way engineers explore a lib in a notebook.
The replacement, inside a Databricks Git Folder:

```python
%pip install -e /Workspace/Repos/<your-user>/mono-dev/libs/de_toolbox
dbutils.library.restartPython()
```

Editable, scoped to that notebook session, and — unlike the shared path — visible
to nobody else. Local development is unchanged: the uv workspace already resolves
`libs/*` for `pytest` and `mypy`.

### Migration

1. Add the `artifacts` + `libraries` blocks to the project scaffold template so new
   projects get this by default. (`make new-project`)
2. Rewrite `.claude/rules/lib-imports.md`, `libs/AGENTS.md`, and the three skills
   that currently instruct agents to emit `sys.path.append`.
3. Add a lint check that fails on `sys.path.append` pointing at a workspace path.
4. Retrofit existing projects — **there are none**, which is why this is being
   settled now rather than later.

## Alternatives considered

**Publish versioned wheels to a registry; consumers pin `de-toolbox==0.4.2`.**
Better isolation in principle, and the right answer if these libs ever gain
consumers outside this repo. Rejected for now: Artifactory is blocked, and it
introduces a second version axis on top of the git ref — every question becomes
"which ref *and* which lib version" — while making atomic lib-plus-consumer
changes impossible in a single MR. Revisit when a registry exists or an external
consumer appears.

**Publish wheels to a Unity Catalog Volume, reference by path.** Works without
Artifactory, but reintroduces the original problem in a new location: a mutable
shared path that a deploy can move underneath a project that was not deployed.

**Keep `sys.path.append`, accept the coupling.** Would mean deleting the
independent-promotion claim from the release model rather than fixing it. The
coupling is silent and untestable, which is the worst property a dependency can
have.

## See also

- `docs/adr/0003-shared-library-layout.md` — the `src/` layout this amends
- `docs/superpowers/specs/2026-09-01-modular-release-model-design.md` — the release model this unblocks
- `.claude/rules/lib-imports.md` — the consumption rules
- `libs/AGENTS.md` — the library registry
