# Testing

## Three layers

| Layer | Lives in | Runs in | When |
|---|---|---|---|
| **Unit** | `tests/unit/` | pytest, no Spark | Every commit, fast (<10s per app) |
| **Integration** | `tests/integration/` | pytest with Spark fixture | Every MR, slower (~30s per app) |
| **End-to-end** | `tests/e2e/` | DAB on a scratch catalog in dev | Manual + nightly |

## Unit tests — the hard floor

- **Every pure transform is unit-tested.** A transform takes Python data
  (lists, dicts, Pandas), returns Python data. No Spark.
- **Coverage target: 80% line coverage on `src/<package>/transforms.py`.**
  The CI gate fails the MR if coverage drops.
- **Test the boundary, not the implementation.** Give the function
  realistic input, assert on output shape + values.

```python
# tests/unit/test_transforms.py
from finance_payment_recon.transforms import dedupe_by_txn_id

def test_dedupe_keeps_latest():
    rows = [
        {"txn_id": "A", "amount": 100, "ts": 1},
        {"txn_id": "A", "amount": 110, "ts": 2},  # later — wins
        {"txn_id": "B", "amount":  50, "ts": 1},
    ]
    out = dedupe_by_txn_id(rows)
    assert len(out) == 2
    assert {r["txn_id"]: r["amount"] for r in out} == {"A": 110, "B": 50}
```

## Integration tests — Spark fixture

- **Use the `spark_fixture`** from `libs/common-test` (you'll create it
  on first need). Module-scoped — one Spark session per test module.
- **Test the IO boundary**: schema enforcement, partition pruning,
  MERGE semantics.
- **Use the `tmp_catalog` fixture** for tables; never touch real catalogs.

```python
# tests/integration/test_io.py
def test_writes_to_silver_with_schema(spark_fixture, tmp_catalog):
    df = spark_fixture.createDataFrame([(1, "ok")], "id INT, status STRING")
    write_silver(df, table=f"{tmp_catalog}.test_table")
    result = spark_fixture.table(f"{tmp_catalog}.test_table").collect()
    assert len(result) == 1
    assert result[0]["status"] == "ok"
```

## Property-based tests — when shape matters

Use `hypothesis` for invariants you want to hold across many inputs:

```python
from hypothesis import given, strategies as st

@given(st.lists(st.dictionaries(...)))
def test_dedupe_idempotent(rows):
    once = dedupe_by_txn_id(rows)
    twice = dedupe_by_txn_id(once)
    assert once == twice
```

## What NOT to test

- **Spark itself.** Don't write tests asserting that `df.filter(...)`
  returns the right rows. Test your transform, not Spark.
- **Third-party libraries.** Trust pandas, requests, boto3.
- **Database / Lakebase / external APIs in unit tests.** Mock them; test
  the integration separately.

## dbt-style data tests (when you have SQL transforms)

Even without dbt, write data tests as `pytest` cases against the dev
catalog:

- Every PK column has `not_null` + `unique` assertions.
- Every FK has a `referential` check (no orphans).
- Every classification-tagged column has a `mask_function` test (the
  mask returns null for unauthorised users).

## CI gates

- **Unit tests fail the MR.**
- **Coverage drop > 2% fails the MR.**
- **Integration tests fail the MR.**
- **E2E tests are reported but don't block** — they catch infra issues,
  not code issues.
