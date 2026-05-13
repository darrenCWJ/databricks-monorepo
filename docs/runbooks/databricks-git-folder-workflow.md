# Runbook: working from a Databricks Git Folder

Engineers often edit notebooks directly in the Databricks workspace UI
and push from there via the Git Folder integration. This bypasses local
pre-commit hooks; CI catches everything anyway, but the feedback loop is
slower. Three patterns to bridge the gap.

## When to use this

- You're on a locked-down government machine where you can't install
  `uv`, `just`, or the Databricks CLI locally.
- You're prototyping a notebook and want immediate execution in
  Databricks.
- You're using **Genie Code** or **Databricks Code Assistant** as your
  agent (see `docs/runbooks/databricks-code-assistant.md`).

## The basic flow

1. Workspace → Repos → Add Repo → paste your GitLab repo URL +
   credentials (set up once via Linked Accounts).
2. The Git Folder appears at `/Workspace/Repos/<user>/cdo-platform/`.
3. Edit, run, iterate in notebooks.
4. Workspace → Repos → Git operations → commit + push to feature branch.
5. Open MR in GitLab from the pushed branch.

## What's missing (and how to recover)

Pre-commit hooks don't fire from Databricks pushes. The hooks live in
`.git/hooks/pre-commit` on the laptop that runs `git commit`, and the
Databricks workspace isn't that laptop.

Three options to recover the local feedback:

### Option A — Pre-push validation notebook (recommended)

Add a scratch cell to any notebook before pushing:

```python
%pip install --quiet pre-commit uv
import subprocess

result = subprocess.run(
    ["pre-commit", "run", "--all-files"],
    cwd="/Workspace/Repos/<user>/cdo-platform",
    capture_output=True, text=True,
)
print(result.stdout)
print(result.stderr)
if result.returncode != 0:
    raise SystemExit(
        f"Pre-commit failed (exit {result.returncode}). "
        "Fix the issues, save, re-run this cell before pushing."
    )
print("All pre-commit checks passed. Safe to push.")
```

Run-this-cell-before-push becomes the workflow. Same hooks, same exit
codes, same error messages as on a laptop. Cost: ~30-60 seconds per run.

### Option B — Pre-push job (zero developer friction)

Define a Databricks Job in `apps/<team>-pre-push-validate/bundle.yml`
that runs the same checks. Require its green status in the Git Folder UI
before allowing push. Enforced rather than voluntary. Cost: cluster
startup (~1-2 min per check) but no engineer discipline required.

### Option C — Skip; rely on CI

Push directly. CI fails 3-5 minutes later if there's a problem. Fix in
the notebook, push again. Acceptable for low-frequency edits; painful for
tight iteration loops.

## What CI catches regardless of origin

| Layer | Catches |
|---|---|
| `pre-commit run --all-files` (CI stage) | Lint, classification, AGENTS.md drift, cross-team imports |
| `compute-affected` + `test-python` / `test-scala` / `test-dbt` | Test regressions, dbt parse failures |
| `bundle-validate` | DAB syntax errors, missing service principals |
| `security` (pip-audit, trivy, ruff -S) | Vulnerabilities |
| CODEOWNERS-driven review | Human approval gates |

Nothing reaches main without passing these — regardless of whether the
push came from a laptop, a Databricks Git Folder, Genie Code, or any
other agent.

## Tight iteration without local tools

For engineers who can never install local tools (constrained machines),
the practical workflow:

1. Open Databricks. Clone the Git Folder.
2. Edit in notebooks.
3. Run Option A's pre-push cell every few commits.
4. Push feature branch.
5. Open MR. CI runs.
6. Review failures in the GitLab UI. Fix in the same notebook. Push again.
7. CODEOWNER approves. Merge.

You never need a laptop with `uv` / `just` / `databricks` installed. The
platform supports this path natively.

## What about agents that author from inside Databricks?

Genie Code and Databricks Code Assistant write code directly into the
notebook. The push lifecycle is identical: their suggestions land in the
Git Folder, you run Option A's pre-push cell, you push, CI fires.

The MR is treated like any human-authored MR — no special "agent
approved" path. CODEOWNERS routes review to the right team. The cleared
reviewer signs off if any Restricted column was touched.

## See also

- `docs/runbooks/databricks-code-assistant.md` — agent-specific guidance
- `docs/runbooks/bootstrap-ci-and-audit.md` Part 2 — Databricks ↔ GitLab
- `AGENTS.md` — repo rules every contributor follows
