# Best practices

Evergreen patterns. Not how-to guides (those live in `runbooks/`).
Read these once when joining; refer back when you hit a question.

| File | Topic |
|---|---|
| `code-style.md` | Python + Scala conventions. |
| `data-modeling.md` | Schemas, partitioning, naming. |
| `testing.md` | What to unit-test, what to integration-test, fixtures. |
| `secrets-and-config.md` | Secret scopes, config layers, env vars. |
| `notebooks.md` | `src/`, `notebooks/`, and the thin-shim pattern. |
| `performance.md` | Spark tuning, partitioning, broadcast joins, AQE. |
| `observability.md` | Logging, metrics, alerting. |
| `security.md` | Least privilege, PII handling, classification. |
| `cost-management.md` | Cluster sizing, autoscaling, job concurrency. |
| `data-contracts.md` | How writes are governed by upstream/downstream contracts. |

Want to add one? Open an MR. Each page is ≤ 200 lines, prose-first,
with code examples only where they're load-bearing.
