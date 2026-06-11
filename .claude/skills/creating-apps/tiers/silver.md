# Silver / Transform Tier — Phase 4

## Step 4a: Show Bronze schema, ask about silver tables (all in one message)

Display every bronze table and cross-app Delta read defined in Phase 3, then ask:

```
Silver tier — let's design the transformation layer.

Available inputs from Bronze:
  A) <catalog>.bronze.<name_a>   fields: <field1>, <field2>, ...
  B) <catalog>.bronze.<name_b>   fields: ...
  C) <catalog>.<schema>.<table>  (cross-app Delta read)

─── TABLE STRUCTURE ──────────────────────────────────────────

1. How many silver output tables will this app produce?
   List each with a short description:
   e.g.  A) silver.payments — cleaned payment rows
         B) silver.payments_quarantine — failed quality rows

2. For each silver table, answer:
   a) Which bronze input(s) does it read from?
      - One input → straight transform
      - Multiple inputs → join/merge (specify join keys)
   b) Does any silver table feed another silver table?
      (e.g. silver_summary reads from silver_payments — type yes/no)

─── PER-TABLE DESIGN ──────────────────────────────────────────

For each silver table:

3. Quality rules — fields that must pass to reach silver
   Rule options: NOT NULL | > 0 | IN [list] | regex | range [min,max]
   Action options: quarantine (separate table) | drop row | fail job
   e.g.  payment_id: NOT NULL → quarantine
         amount: > 0 → quarantine

4. Deduplication
   1. Yes — on key field(s)? Keep: latest / first (by which timestamp?)
   2. No

5. Derived fields — new columns to compute
   e.g.  amount_sgd = amount * fx_rate   — or "none"

6. Table name
   Recommended: `<catalog>.silver.<description>`  — confirm or change

7. Quarantine table name  (if any rules use quarantine action)
   Recommended: `<catalog>.silver.<description>_quarantine`

─── TASK STRUCTURE ────────────────────────────────────────────

8. Task structure  (only if 2+ silver tables with no sequential dependency)
   1. One combined silver task  (tables built sequentially in one cluster)
   2. Separate task per silver table  (parallel execution, independent retry)
```

---

## Step 4b: Present Silver design — wait for confirmation

```
SILVER DESIGN
─────────────────────────────────────────────────────────────────
Table A: <catalog>.silver.<name_a>
  Reads from : <catalog>.bronze.<name>  [+ <catalog>.bronze.<name_b> JOIN ON <key>]
  Quality rules:
    <field>  <rule>  → <action>
  Deduplication: on <key>, keep <latest | first> by <ts>  — OR —  none
  Derived fields:
    <new_field> = <expression>
  Quarantine: <catalog>.silver.<name_a>_quarantine  — OR —  none

Table B: <catalog>.silver.<name_b>
  Reads from : <catalog>.silver.<name_a>  (sequential — depends on Table A)
  ...  — OR —  none

Task structure:
  <1 combined task "silver">  — OR —  <separate tasks: "silver_a", "silver_b" [parallel | sequential]>
─────────────────────────────────────────────────────────────────
Confirm or correct before code is written.
```

---

## Step 4c: Write Silver code (after confirmation only)

**File layout:**
- One combined task → `src/<pkg>/silver.py`; `run(catalog, run_date)` calls all transforms in order
- Separate tasks → `src/<pkg>/silver_<name>.py` per table, each with its own `run(...)`
- Notebooks are thin shims only

---

### Implementation patterns

#### Single bronze input — transform + quality split
```python
import datetime as dt
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

def transform_<name>(catalog: str, run_date: dt.date) -> tuple[DataFrame, DataFrame]:
    spark = SparkSession.getActiveSession()
    bronze = spark.read.table(f"{catalog}.bronze.<name>")

    # Drop Auto Loader metadata if present (file-sourced bronze only)
    if "_has_errors" in bronze.columns:
        bronze = bronze.filter(F.col("_has_errors") == False)

    # Deduplication — keep latest record per business key
    window = Window.partitionBy("<key_field>").orderBy(F.desc("ingestion_date"))
    deduped = (
        bronze
        .withColumn("_rn", F.row_number().over(window))
        .filter(F.col("_rn") == 1)
        .drop("_rn", "_rescued_data", "_has_errors", "_source_file")
    )

    # Type casting + derived fields
    typed = (
        deduped
        .withColumn("<money_field>", F.col("<money_field>").cast("DECIMAL(18,2)"))
        .withColumn("<date_field>",  F.col("<date_field>").cast("DATE"))
        .withColumn("<derived>",     <expression>)
    )

    # Quality split
    passes = (
        F.col("<field_a>").isNotNull() &
        (F.col("<field_b>") > 0) &
        F.col("<field_c>").isin([...])
    )
    return typed.filter(passes), typed.filter(~passes)


def run(catalog: str, run_date: dt.date) -> None:
    silver_df, quarantine_df = transform_<name>(catalog, run_date)

    (silver_df.write.format("delta").mode("append")
     .partitionBy("ingestion_date")
     .saveAsTable(f"{catalog}.silver.<name>"))

    if not quarantine_df.isEmpty():
        (quarantine_df.write.format("delta").mode("append")
         .partitionBy("ingestion_date")
         .saveAsTable(f"{catalog}.silver.<name>_quarantine"))
```

#### Multiple bronze inputs — join then transform
```python
def transform_<name>(catalog: str, run_date: dt.date) -> tuple[DataFrame, DataFrame]:
    spark = SparkSession.getActiveSession()
    df_a = spark.read.table(f"{catalog}.bronze.<name_a>")
    df_b = spark.read.table(f"{catalog}.bronze.<name_b>")

    if "_has_errors" in df_a.columns:
        df_a = df_a.filter(F.col("_has_errors") == False)
    if "_has_errors" in df_b.columns:
        df_b = df_b.filter(F.col("_has_errors") == False)

    joined = df_a.join(df_b, on="<join_key>", how="<inner|left>")
    # ... dedup, type cast, quality split same as above
```

---

**Tests (per silver table):**
- One passing row goes through cleanly, lands in silver only
- One row per failing quality rule lands in quarantine, not silver
- Deduplication keeps the correct row (latest by timestamp) when duplicates present
- Derived fields compute correctly
- Join produces expected output rows (if inputs are merged)
