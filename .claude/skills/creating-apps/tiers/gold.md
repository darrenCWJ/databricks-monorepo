# Gold / Serving Tier — Phase 5

## Step 5a: Show Silver schema, ask about gold tables (all in one message)

Display every silver table defined in Phase 4, then ask:

```
Gold tier — let's design the serving layer.

Available inputs from Silver:
  A) <catalog>.silver.<name_a>   fields: <field1>, <field2>, ...
  B) <catalog>.silver.<name_b>   fields: ...

─── TABLE STRUCTURE ──────────────────────────────────────────

1. How many gold output tables will this app produce?
   List each with a short description:
   e.g.  A) gold.payment_summary — daily totals by currency for Tableau
         B) gold.payment_exceptions — row-level discrepancies for ops team

2. For each gold table, answer:
   a) Which silver input(s) does it read from?
      - One input → aggregate or pass-through
      - Multiple inputs → join/merge (specify join keys)
   b) Does any gold table feed another gold table?
      (e.g. gold_report reads from gold_summary — type yes/no)

─── PER-TABLE DESIGN ──────────────────────────────────────────

For each gold table:

3. What does the business want to see?
   Describe in plain English.
   e.g. "Daily totals by currency with flagged discrepancy counts."

4. Dimensions — fields to group by
   e.g.  reconciliation_date, currency, region

5. Metrics — what to measure
   For each: name, aggregation, source field
   e.g.  total_amount     = SUM(amount)
         payment_count    = COUNT(payment_id)
         discrepancy_count = SUM(CASE WHEN is_discrepancy THEN 1 ELSE 0)
   Or type "none" for row-level (no aggregation)

6. Time grain
   1. Daily  2. Weekly  3. Monthly  4. None (row-level)

7. Write mode
   1. Full refresh  (recommended for aggregated tables)
   2. Incremental append  (for row-level or high-volume tables)

8. Gold table name
   Recommended: `<catalog>.gold.<description>`  — confirm or change

9. Downstream consumers  (optional)
   e.g.  Tableau dashboard, downstream DAB job, data science team
   Or type "unknown"

─── TASK STRUCTURE ────────────────────────────────────────────

10. Task structure  (only if 2+ gold tables with no sequential dependency)
    1. One combined gold task  (tables built sequentially in one cluster)
    2. Separate task per gold table  (parallel execution, independent retry)
```

---

## Step 5b: Present Gold design — wait for confirmation

```
GOLD DESIGN
─────────────────────────────────────────────────────────────────
Table A: <catalog>.gold.<name_a>
  Reads from  : <catalog>.silver.<name>  [+ <catalog>.silver.<name_b> JOIN ON <key>]
  Dimensions  : <field1>, <field2>
  Metrics     : <metric> = <aggregation>
  Time grain  : <daily | weekly | monthly | row-level>
  Write mode  : <full-refresh | incremental>
  Consumers   : <listed consumers | none>

Table B: <catalog>.gold.<name_b>
  Reads from  : <catalog>.gold.<name_a>  (sequential — depends on Table A)
  ...  — OR —  reads from silver (independent)

Task structure:
  <1 combined task "gold">  — OR —  <separate tasks: "gold_a", "gold_b" [parallel | sequential]>
─────────────────────────────────────────────────────────────────
Confirm or correct before code is written.
```

---

## Step 5c: Write Gold code (after confirmation only)

**File layout:**
- One combined task → `src/<pkg>/gold.py`; `run(catalog, run_date)` calls all builds in order
- Separate tasks → `src/<pkg>/gold_<name>.py` per table, each with its own `run(...)`
- Notebooks are thin shims only

---

### Implementation patterns

#### Aggregated table — full refresh (small daily summary)
Overwrites the whole table each run. Simple, no partition logic needed.
```python
import datetime as dt
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F

def build_<name>(catalog: str, run_date: dt.date) -> DataFrame:
    spark = SparkSession.getActiveSession()
    silver = spark.read.table(f"{catalog}.silver.<name>")

    gold = (
        silver
        .groupBy("<dim1>", "<dim2>")
        .agg(
            F.sum("<amount_field>").alias("<total_metric>"),
            F.count("*").alias("<count_metric>"),
            F.sum(F.when(F.col("<flag_field>"), 1).otherwise(0)).alias("<flag_count>"),
        )
    )

    (gold.write.format("delta")
     .mode("overwrite")
     .option("overwriteSchema", "true")
     .saveAsTable(f"{catalog}.gold.<name>"))
    return gold
```

#### Aggregated table — date-partitioned replace (recommended for daily agg tables)
Only overwrites today's partition. Safe to rerun without touching historical data.
```python
def build_<name>(catalog: str, run_date: dt.date) -> DataFrame:
    spark = SparkSession.getActiveSession()
    silver = (
        spark.read.table(f"{catalog}.silver.<name>")
        .filter(F.col("ingestion_date") == str(run_date))
    )

    gold = (
        silver
        .groupBy("<date_col>", "<dim>")
        .agg(F.sum("<field>").alias("<metric>"), ...)
    )

    # replaceWhere rewrites only today's slice — idempotent reruns
    (gold.write.format("delta")
     .mode("overwrite")
     .option("replaceWhere", f"<date_col> = '{run_date}'")
     .saveAsTable(f"{catalog}.gold.<name>"))
    return gold
```

#### Row-level table (no aggregation — ops/exception feeds, high-volume consumers)
Appends only today's rows. Use when consumers need every row, not summaries.
```python
def build_<name>(catalog: str, run_date: dt.date) -> DataFrame:
    spark = SparkSession.getActiveSession()
    gold = (
        spark.read.table(f"{catalog}.silver.<name>")
        .filter(F.col("ingestion_date") == str(run_date))
        .withColumn("<enriched_field>", <expression>)
        .select("<col1>", "<col2>", ...)   # expose only columns consumers need
    )

    (gold.write.format("delta").mode("append")
     .partitionBy("ingestion_date")
     .saveAsTable(f"{catalog}.gold.<name>"))
    return gold
```

#### Multiple silver inputs — join before aggregating
```python
def build_<name>(catalog: str, run_date: dt.date) -> DataFrame:
    spark = SparkSession.getActiveSession()
    df_a = spark.read.table(f"{catalog}.silver.<name_a>")
    df_b = spark.read.table(f"{catalog}.silver.<name_b>")
    joined = df_a.join(df_b, on="<join_key>", how="<inner|left>")
    # ... then aggregate or pass through as above
```

---

**Tests (per gold table):**
- Metric values correct against a known input dataset
- Row count matches expected grain (one row per dimension combination)
- `replaceWhere` / full-refresh produces no duplicate rows on re-run
- Join produces expected output rows when multiple silver inputs are merged
