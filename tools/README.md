# tools/

Platform-team scripts that operate on the whole repo. Not application
code — these are CI helpers, audit utilities, and scaffolding.

| File | What it does |
|---|---|
| `scripts/scaffold.py` | Generate new app / lib folder skeletons. |
| `scripts/audit_log.py` | Append a deploy record to the WORM S3 audit bucket. |
| `scripts/check_boundaries.py` | Pre-commit check: no cross-team imports. |
| `scripts/check_pii_contract.py` | Pre-commit: every Restricted column has a mask. |
| `scripts/lint_agents_md.py` | Pre-commit: AGENTS.md present + under 200 lines. |
| `scripts/where_is.py` | "Which app writes this table?" |
| `scripts/affected.py` | Compute affected projects from a git diff. |
