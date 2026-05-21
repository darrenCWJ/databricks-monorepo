# CDO Platform Monorepo — Claude Code

@AGENTS.md

## Agent Delegation

Use agents proactively — do not wait for the user to ask:

| Trigger | Agent(s) | Action |
|---------|----------|--------|
| New feature / pipeline request | `planner` | Plan before coding. Identify affected scopes via `just affected`. |
| Any code written or modified | `code-reviewer` | Review immediately after changes. |
| New app, lib, or function | `tdd-guide` | Write tests first. Verify 80%+ coverage. |
| Architectural decision | `architect` | Evaluate trade-offs, produce ADR if significant. |
| Security-sensitive code (auth, grants, PII, masks) | `security-reviewer` | BLOCK commit until CRITICAL issues resolved. |
| Build or lint failure | `build-error-resolver` | Fix incrementally, verify after each fix. |
| Terraform / Unity Catalog changes | `security-reviewer` + `architect` | Both required — parallel review. |
| Python code changes | `python-reviewer` | PEP 8, type hints, PySpark idioms, ruff compliance. |
| Refactoring or dead code | `refactor-cleaner` | Identify and remove unused code safely. |

## Skills (invoke via `/skill-name`)

### Databricks (from AI Dev Kit — installed globally)
- `databricks-bundles` — DAB authoring, targets, variables, includes
- `databricks-python-sdk` — SDK, Databricks Connect, CLI, REST API
- `databricks-dbsql` — SQL warehouses, materialized views, AI functions
- `databricks-unity-catalog` — Catalogs, schemas, grants, lineage
- `databricks-jobs` — Job configuration, scheduling, clusters
- `databricks-spark-structured-streaming` — Streaming pipelines, Kafka, triggers
- `databricks-spark-declarative-pipelines` — DLT / declarative pipelines

### Python Development
- `python-patterns` — Idiomatic Python, type hints, async
- `python-testing` — pytest, TDD, fixtures, mocking, parametrization
- `tdd-workflow` — Red-Green-Refactor cycle enforcement
- `security-review` — OWASP, secrets, injection, unsafe patterns

### CI / Git / Deployment
- `git-workflow` — Branching, commits, conflict resolution
- `deployment-patterns` — CI/CD, environments, rollback strategies

## Workflow Checklist

Before any code change:
1. `just affected` — understand blast radius
2. Read per-folder `AGENTS.md` for the directory being edited
3. For data writes: verify target table's `mask_function` if `Restricted`

Before suggesting a commit:
1. `just lint PATH && just test PATH` must pass
2. `code-reviewer` agent must approve (no CRITICAL/HIGH issues)
3. For infra: `security-reviewer` must approve

## Parallel Agent Patterns

For complex tasks, spawn agents in parallel:
- Security analysis + code review + test coverage (3 agents simultaneously)
- Architecture evaluation + performance review (2 agents simultaneously)
- Never run sequentially when agents are independent
