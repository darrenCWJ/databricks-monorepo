# Data Migration (Phase 4b)

Skip this phase entirely if the user selected Intent 1, 3, or 4 in Phase 1.
Enter here after Phase 3+4 are complete (connection + auth established to Lakebase).

**Important:** Data migration ALWAYS uses PostgreSQL wire protocol for bulk import,
even if the app will use Data API afterward. The Data API is not designed for bulk
loading (one POST per row is too slow for thousands of rows). After migration
completes, the app connects via its chosen method (Data API or PG wire).

---

## Detect Source Database

Scan for existing database signals:
- `DATABASE_URL` in `.env` → parse dialect (postgres, mysql, sqlite)
- `docker-compose.yml` → service names (postgres, mysql, mongo)
- ORM config → connection strings, engine declarations
- Existing migration files → tool + dialect

If not detectable, ask:

> "What's your current (source) database?
> 1. **PostgreSQL** (Supabase, Neon, RDS, self-hosted)
> 2. **MySQL / MariaDB**
> 3. **SQLite**
> 4. **MongoDB** (document → relational mapping needed)
> 5. **Other** (describe)"

---

## Migration Scope Scan (MANDATORY before any export/import)

Before starting the migration, connect to the source database and scan its contents.
Present the results to the user so they know exactly what will be migrated.

**Run against the source database:**

```sql
-- PostgreSQL: list all user tables with row counts
SELECT
  schemaname || '.' || relname AS table_name,
  n_live_tup AS row_count
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC;

-- MySQL: list all tables with row counts
SELECT
  table_name,
  table_rows AS row_count
FROM information_schema.tables
WHERE table_schema = DATABASE()
ORDER BY table_rows DESC;

-- SQLite: list tables (row counts require per-table COUNT(*))
SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%';
```

**Present to the user:**

> "Here's what will be migrated from your source database:
>
> | Table | Rows |
> |-------|------|
> | users | 15,234 |
> | orders | 89,012 |
> | order_items | 234,567 |
>
> **Total:** 3 tables, 338,813 rows
>
> Would you like to proceed with migrating all tables, or exclude any?"

---

## Path A — One-Time Copy

Full dump-and-load with cutover.

**Step 1: Export from source**

```bash
# PostgreSQL → PostgreSQL (most common for Lakebase)
pg_dump --no-owner --no-privileges --schema-only -f schema.sql "$SOURCE_DATABASE_URL"
pg_dump --no-owner --no-privileges --data-only --format=csv -f data/ "$SOURCE_DATABASE_URL"

# MySQL → PostgreSQL (requires schema translation)
mysqldump --no-create-info --tab=/tmp/export --fields-terminated-by=',' source_db
```

**Step 2: Schema adaptation**

> Invoke `database-migrations` skill for type mapping if source != PostgreSQL.

Common type mappings (MySQL → Lakebase/PostgreSQL):

| MySQL | PostgreSQL |
|---|---|
| `INT AUTO_INCREMENT` | `SERIAL` or `INTEGER GENERATED ALWAYS AS IDENTITY` |
| `TINYINT(1)` | `BOOLEAN` |
| `DATETIME` | `TIMESTAMP` |
| `TEXT` / `LONGTEXT` | `TEXT` |
| `ENUM(...)` | `TEXT CHECK (col IN (...))` or custom enum type |
| `JSON` | `JSONB` |

**Step 3: Import into Lakebase**

```python
# scripts/import_to_lakebase.py
import csv
import os
from pathlib import Path
from db.connection import get_conn

DATA_DIR = Path("data/")

def import_table(table_name: str, csv_path: Path, allowed_tables: set[str]) -> int:
    if table_name not in allowed_tables:
        raise ValueError(f"Table '{table_name}' not in allowlist")
    with get_conn() as conn:
        with conn.cursor() as cur:
            with open(csv_path) as f:
                reader = csv.reader(f)
                headers = next(reader)
                from psycopg import sql
                insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier(table_name),
                    sql.SQL(", ").join(sql.Identifier(h) for h in headers),
                    sql.SQL(", ").join(sql.Placeholder() for _ in headers),
                )
                rows = list(reader)
                for i in range(0, len(rows), 1000):
                    batch = rows[i:i+1000]
                    cur.executemany(insert_query, batch)
            conn.commit()
    return len(rows)

# Import tables in dependency order (parents before children)
IMPORT_ORDER = ["users", "orders", "order_items"]  # adjust to your schema
ALLOWED_TABLES = set(IMPORT_ORDER)

for table in IMPORT_ORDER:
    csv_file = DATA_DIR / f"{table}.csv"
    if csv_file.exists():
        count = import_table(table, csv_file, ALLOWED_TABLES)
        print(f"  {table}: {count} rows imported")
```

**Step 4: Row Count Verification**

```python
from psycopg import sql
from db.connection import get_conn

SOURCE_COUNTS = {
    "users": 15234,       # fill from source scan
    "orders": 89012,
    "order_items": 234567,
}

with get_conn() as conn:
    with conn.cursor() as cur:
        for table, expected in SOURCE_COUNTS.items():
            cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table)))
            actual = cur.fetchone()[0]
            status = "PASS" if actual == expected else "FAIL"
            print(f"  [{status}] {table}: expected={expected} actual={actual}")
```

If any FAIL: investigate before proceeding.

**Step 5: Live Connection Verification (Interactive)**

After the app's `.env` is updated to point to Lakebase, ask:

> "Would you like to verify that your app is actually pulling data from Lakebase?
> I'll insert a temporary test row, you check if it shows up, then I'll delete it."

If user says yes:

1. Insert a canary row:
```sql
INSERT INTO <first_table> (<text_column>)
VALUES ('__lakebase_migration_verify__');
```

2. Tell user to check their app and Databricks UI for the test row.

3. After confirmation, delete it:
```sql
DELETE FROM <first_table> WHERE <text_column> = '__lakebase_migration_verify__';
```

4. If not visible: diagnose `.env`, app restart, connection file imports.

**Step 6: Cutover checklist**

- [ ] All tables imported with correct row counts
- [ ] Live verification passed (app reads from Lakebase)
- [ ] Foreign key constraints valid (no orphaned references)
- [ ] Sequences reset to max(id) + 1 for each table
- [ ] Application `.env` updated to point to Lakebase
- [ ] Old database connection removed from app config
- [ ] Old database kept read-only for 7 days as rollback safety net
- [ ] Old database decommissioned after verification period

---

## Path B — Dual-Run (Replication)

Both databases stay live. Writes go to source, replicated to Lakebase (or vice versa).

**Strategy options:**

| Strategy | Latency | Complexity | Best for |
|---|---|---|---|
| CDC (Change Data Capture) | Near real-time | High | Production replication |
| Scheduled sync (cron) | Minutes to hours | Low | Analytics, reporting |
| Dual-write in app | Real-time | Medium | Small tables, critical data |

**Option 1: Scheduled sync (simplest)**

```python
# scripts/sync_to_lakebase.py
import os
from datetime import datetime, timedelta
from db.connection import get_conn as get_lakebase_conn
import psycopg

SYNC_WINDOW = timedelta(minutes=10)

def get_source_conn():
    return psycopg.connect(os.environ["SOURCE_DATABASE_URL"])

ALLOWED_SYNC_TABLES = {"users", "orders"}  # UPDATE with your tables

def sync_table(table: str, timestamp_col: str = "updated_at") -> int:
    if table not in ALLOWED_SYNC_TABLES:
        raise ValueError(f"Table '{table}' not in sync allowlist")
    from psycopg import sql
    since = datetime.utcnow() - SYNC_WINDOW
    synced = 0
    batch_size = 1000

    with get_source_conn() as source:
        with source.cursor(name="sync_cursor") as cur:
            cur.itersize = batch_size
            cur.execute(
                sql.SQL("SELECT * FROM {} WHERE {} >= %s").format(
                    sql.Identifier(table), sql.Identifier(timestamp_col)
                ),
                (since,),
            )
            cols = [d.name for d in cur.description]
            insert_query = sql.SQL(
                "INSERT INTO {} ({}) VALUES ({}) ON CONFLICT (id) DO UPDATE SET {}"
            ).format(
                sql.Identifier(table),
                sql.SQL(", ").join(sql.Identifier(c) for c in cols),
                sql.SQL(", ").join(sql.Placeholder() for _ in cols),
                sql.SQL(", ").join(
                    sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c))
                    for c in cols if c != "id"
                ),
            )

            with get_lakebase_conn() as dest:
                with dest.cursor() as dest_cur:
                    while True:
                        batch = cur.fetchmany(batch_size)
                        if not batch:
                            break
                        dest_cur.executemany(insert_query, batch)
                        synced += len(batch)
                dest.commit()

    return synced

TABLES_TO_SYNC = ["users", "orders"]

for table in TABLES_TO_SYNC:
    count = sync_table(table)
    print(f"  {table}: {count} rows synced")
```

**Option 2: Dual-write pattern (application-level)**

```python
# middleware/dual_write.py
import logging
import threading
from psycopg import sql
from db.connection import get_conn as get_lakebase_conn

logger = logging.getLogger(__name__)

ALLOWED_TABLES = {"users", "orders", "products"}  # UPDATE

def dual_write(source_result: dict | None, table: str, operation: str, data: dict):
    """Call after successful write to source DB. Runs in background thread."""
    if operation == "insert" and source_result and "id" not in data:
        data = {**data, "id": source_result.get("id")}
    threading.Thread(
        target=_dual_write_sync,
        args=(table, operation, data),
        daemon=True,
    ).start()

def _dual_write_sync(table: str, operation: str, data: dict):
    if table not in ALLOWED_TABLES:
        logger.error(f"Dual-write rejected: table '{table}' not in allowlist")
        return
    try:
        with get_lakebase_conn() as conn:
            with conn.cursor() as cur:
                if operation == "insert":
                    cols = list(data.keys())
                    query = sql.SQL(
                        "INSERT INTO {} ({}) VALUES ({}) ON CONFLICT (id) DO NOTHING"
                    ).format(
                        sql.Identifier(table),
                        sql.SQL(", ").join(sql.Identifier(c) for c in cols),
                        sql.SQL(", ").join(sql.Placeholder() for _ in cols),
                    )
                    cur.execute(query, tuple(data.values()))
                elif operation == "update":
                    cols = list(data.keys())
                    update_cols = [k for k in cols if k != "id"]
                    query = sql.SQL("UPDATE {} SET {} WHERE id = %s").format(
                        sql.Identifier(table),
                        sql.SQL(", ").join(
                            sql.SQL("{} = %s").format(sql.Identifier(c))
                            for c in update_cols
                        ),
                    )
                    cur.execute(query, (*[data[k] for k in update_cols], data["id"]))
                elif operation == "delete":
                    query = sql.SQL("DELETE FROM {} WHERE id = %s").format(
                        sql.Identifier(table),
                    )
                    cur.execute(query, (data["id"],))
                else:
                    logger.warning(f"Dual-write: unknown operation '{operation}'")
                    return
            conn.commit()
    except Exception as e:
        logger.warning(f"Dual-write to Lakebase failed: {e}")
```

**Conflict resolution:** If both databases accept writes, define a winner:
- Last-write-wins (by `updated_at`)
- Source-is-primary (Lakebase is read-only replica)
- Lakebase-is-primary (source becomes read-only, for gradual cutover)

---

## Path C — Gradual Migration

Move table by table. App reads from both databases during transition.

**Step 1: Migration order**

Prioritize tables with no foreign key dependencies first:

```
Phase 1: Independent tables (users, categories, settings)
Phase 2: Tables with FK to Phase 1 (orders → users)
Phase 3: Join/junction tables (order_items → orders)
```

**Step 2: Dual-read router**

```python
# db/router.py
import os
from db.connection import get_conn as get_lakebase_conn
import psycopg

MIGRATED_TABLES = set(t for t in os.environ.get("MIGRATED_TABLES", "").split(",") if t)

def get_source_conn():
    return psycopg.connect(os.environ["SOURCE_DATABASE_URL"])

def get_read_conn(table: str):
    """Route reads to Lakebase for migrated tables, source for others."""
    if table in MIGRATED_TABLES:
        return get_lakebase_conn()
    return get_source_conn()

def get_write_conn(table: str):
    """Writes always go to the authoritative database for that table."""
    if table in MIGRATED_TABLES:
        return get_lakebase_conn()
    return get_source_conn()
```

**Step 3: Per-table migration process**

For each table:
1. Copy schema to Lakebase (Phase 3 connection already exists)
2. Bulk import existing data (Path A import script)
3. Enable dual-write for that table
4. Verify row counts match
5. Add table to `MIGRATED_TABLES` env var
6. Remove dual-write (Lakebase is now authoritative)

**Step 4: Completion**

When all tables are in `MIGRATED_TABLES`:
- Remove the router — all reads/writes go to Lakebase
- Remove `SOURCE_DATABASE_URL` from config
- Decommission source database
