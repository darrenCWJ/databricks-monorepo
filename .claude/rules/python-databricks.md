# Python + Databricks Rules

## PySpark

- Use DataFrame API over raw SQL when logic is complex or requires type safety.
- Always qualify table names: `catalog.schema.table`.
- Never use f-strings in SQL — use parameterized queries or `spark.sql()` with named params.
- Use `DeltaTable.merge()` for upserts, never DELETE + INSERT.
- No `autoMerge` globally — scope per write with `.option("mergeSchema", "true")`.

## Python Style

- Python 3.11+. Use type hints on all function signatures.
- `ruff` is the linter. Line length: 100.
- No mutable default arguments.
- Use `Decimal` for money, never `float`.
- Prefer `pathlib.Path` over string manipulation for file paths.

## Testing

- pytest with `--strict-markers`.
- Use `testing_utils.spark_fixture` for Spark session in tests.
- Test data transforms with small DataFrames, not mocks of Spark internals.
- Coverage target: 80%+.

## Secrets

- Never hardcode tokens or credentials.
- In notebooks: use `dbutils.secrets.get(scope, key)`.
- In bundle.yml: use `${secrets.scope.key}`.
- In local dev: use environment variables.
