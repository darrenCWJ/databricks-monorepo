---
paths:
  - "**/tests/**"
  - "**/test_*.py"
  - "**/conftest.py"
---
# PySpark Testing Rules

## Test Structure

- Use pytest with `--strict-markers`.
- Follow AAA pattern: Arrange → Act → Assert.
- Organize: `tests/unit/`, `tests/integration/`, `tests/performance/`.
- Coverage target: 80%+.

## Spark Session Fixture

```python
@pytest.fixture(scope="session")
def spark():
    return (SparkSession.builder
        .master("local[2]")
        .appName("test")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate())
```

- Use `scope="session"` to avoid startup cost per test.
- Set `shuffle.partitions=2` for fast local execution.
- Use `local[2]` (2 threads) to catch concurrency issues.

## Testing Transforms

- Test with small DataFrames (3-5 rows), not mocks of Spark internals.
- Compare schemas AND data: assert both `df.schema` and `sorted(df.collect())`.
- Use `spark.createDataFrame()` with explicit schema for test inputs.
- Never mock SparkSession — use a real local session.

## What to Test

- Pure transform functions in `src/` (most valuable).
- Schema correctness after transformation.
- Edge cases: nulls, empty DataFrames, duplicate keys.
- Data type handling: Decimal precision, timestamp zones.
- Error paths: invalid inputs, missing columns.

## What NOT to Test

- Databricks infrastructure (cluster startup, secrets service).
- Third-party library internals (Delta Lake merge correctness).
- Notebook orchestration — test the functions notebooks call.

## Integration Tests

- Use real Spark session with Delta Lake (local mode).
- Write to temporary directories, clean up after.
- Test full read → transform → write pipelines.
- Use `tmp_path` fixture for temp file locations.

## Running Tests

```bash
make test P=apps/<name>          # Run tests for one app
make test P=libs/<name>          # Run tests for one lib
uv run pytest --cov=src --cov-report=term-missing  # With coverage
```
