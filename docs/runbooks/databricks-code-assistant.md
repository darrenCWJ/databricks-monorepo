# Runbook: working with Databricks Code Assistant / Genie Code

Databricks Code Assistant (the inline completion + chat in the Notebook
editor) and **Genie Code** (the agentic, multi-step variant) are AI
coding agents that live inside the Databricks workspace. They join Claude
Code, Cursor, Copilot, Aider, and any internal agentic pipelines as
first-class consumers of this monorepo.

## What's different from CLI agents

| Property | Claude Code (laptop) | Databricks Code Assistant / Genie Code |
|---|---|---|
| Where it runs | Local terminal / IDE | Inside the Databricks workspace |
| Repo access | Reads from local clone | Reads from Databricks Git Folder linked to the repo |
| Pre-commit hooks fire? | Yes (on `git commit`) | No (Databricks's git client doesn't invoke them) |
| CI safety net fires? | Yes (on push) | **Yes — the same CI runs server-side** |
| Live workspace context | None | Sees UC catalogue, cluster state, table samples |
| AGENTS.md auto-loaded? | Yes (via `CLAUDE.md` import) | Depends on the product version — may need explicit prompt |

The platform's governance posture is identical for both. The dev loop
shape is different.

## First-time setup

1. In the Databricks workspace, link your GitLab account (User Settings →
   Linked accounts → GitLab → register PAT). See `docs/runbooks/bootstrap-ci-and-audit.md` Part 2.
2. Clone the repo into a Git Folder:
   - Workspace → Repos → Add Repo → paste your GitLab repo URL.
   - The Git Folder appears under `/Workspace/Repos/<your-username>/cdo-platform/`.
3. Open any notebook inside the Git Folder. Databricks Code Assistant
   activates automatically (Premium / Enterprise plan required).

## Recommended first prompt

Before asking the agent to do anything substantive, give it the rules:

> *"Read `/Workspace/Repos/<your-username>/cdo-platform/AGENTS.md` and the
> per-folder AGENTS.md for the directory I'm working in. Tell me three
> rules you'll follow before suggesting any changes. Then summarize the
> command surface I should use."*

Expected response: a paraphrase of the AGENTS.md rules + a list of `just`
commands. If the agent skips this and just suggests code, the AGENTS.md
context wasn't loaded — paste the relevant sections into the chat before
proceeding.

## The pre-push validation pattern

Pre-commit hooks don't fire from Databricks-side pushes. To get
equivalent local feedback, run `notebooks/_pre_push_check.py` in a
scratch cell before pushing:

```python
%pip install --quiet pre-commit uv
import subprocess
result = subprocess.run(
    ["pre-commit", "run", "--all-files"],
    cwd="/Workspace/Repos/<your-username>/cdo-platform",
    capture_output=True, text=True,
)
print(result.stdout)
print(result.stderr)
assert result.returncode == 0, "Pre-commit failed; fix before pushing"
```

See `docs/runbooks/databricks-git-folder-workflow.md` for the full
Git-Folder push lifecycle.

## What Genie Code does well in this repo

- **Generating new dbt models** — it reads the existing models in
  `dbt/<team>/`, mimics the column-tag pattern, includes `meta.pii`,
  `meta.classification`, etc.
- **Authoring transforms from data shape** — given a UC table, it
  produces idiomatic PySpark or SQL that respects classification.
- **Extending an existing app** — multi-cell edits within one notebook,
  with cluster-aware suggestions (knows what's already installed).

## What it does less well

- **Reasoning across the whole repo.** Cross-team contracts, CODEOWNERS
  routing, the cross-project ref pattern — Genie Code may need to be
  prompted explicitly to consider these.
- **Knowing about `just` and `affected.py`.** It can call them via
  `%sh make affected`, but won't volunteer that. Prompt for it.
- **Notebook hygiene.** Tends to put business logic in the notebook
  rather than wrapping it in `src/`. CODEOWNER review catches this.

## Validation test prompts

Run these in your first session to confirm Genie Code is operating with
the right context.

> **Prompt 1.** "Read AGENTS.md and tell me three rules. Then run
> `make affected` via `%sh` and tell me what would deploy."

> **Prompt 2.** "Open the schema.yml in `dbt/platform-core/models/marts/`.
> Propose adding a column `vat_amount` (DECIMAL(18,2), Restricted PII)
> with full `meta.*` fields. Run `check_pii_contract.py` against your
> proposed change."

> **Prompt 3.** "Without leaving this notebook, scaffold a new Python
> DAB called `finance-payment-recon`. Open the generated bundle.yml
> and confirm it has `run_as` for staging and prod targets."

If all three pass cleanly, the agent is grounded in the repo. If any
fails — typically because AGENTS.md wasn't loaded — start the session
with an explicit context paste.

## Pushing Genie Code-authored changes

Same path as any other Databricks Git Folder push:

1. Run the pre-push notebook (above) — catches what pre-commit would
   have caught.
2. Use the Databricks Git UI: stage, commit, push to a feature branch.
3. Open the MR in GitLab. CI runs the full pre-commit + tests + bundle
   validate + security stage. The 3-5 min CI loop is your enforcement.
4. CODEOWNER approves. Merge. Deploy to dev.

There is no "Genie Code wrote it so it's auto-approved" exception. Same
review path as a human-authored MR.

## Compliance posture

| Concern | Behaviour |
|---|---|
| PII leakage in chat output | Genie Code reads UC schema metadata, not data. Column-level masks apply to any SELECT it runs. |
| Audit trail | Genie Code's executed SQL appears in `system.access.audit` like any other query. Flows to the WORM bucket via `audit_log.py`. |
| Approval routing | CODEOWNERS still applies. Genie Code-authored MRs need the same approvals as human-authored ones. |
| Restricted column changes | `check_pii_contract.py` blocks at CI. Same as any other agent. |

## See also

- `docs/runbooks/databricks-git-folder-workflow.md` — the push lifecycle
- `docs/runbooks/bootstrap-ci-and-audit.md` Part 2 — Databricks ↔ GitLab linkage
- `AGENTS.md` — the rules every agent reads
- `docs/runbooks/access-control.md` — what the agent's generated SQL can and can't see
