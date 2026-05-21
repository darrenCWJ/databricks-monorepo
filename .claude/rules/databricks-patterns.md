---
paths:
  - "**/*.py"
  - "**/*.ipynb"
  - "**/*.sql"
  - "**/databricks.yml"
  - "**/.databricks/**"
---
# Databricks Patterns

> Backend/data-layer constraints for Databricks/Lakebase. Extends [common/patterns.md](../common/patterns.md).

## Connection

- NEVER use raw `SparkSession` — always use `DatabricksSession` (Databricks Connect)
- NEVER hardcode host, token, or cluster_id — read from environment variables only

## Queries

- NEVER use f-strings in SQL — use parameterized queries or DataFrame API
- ALWAYS qualify table names as `catalog.schema.table`, never bare table names

## Data Operations

- ALWAYS use `DeltaTable.merge()` for upserts — never DELETE + INSERT
- NEVER enable `autoMerge` globally — scope it per write with `option("mergeSchema", "true")`

## Secrets

- NEVER hardcode tokens — use `dbutils.secrets` in notebooks, env vars in scripts

## Reference

See skill: `databricks-lakebase` for connection, security, and query patterns.
