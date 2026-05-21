# Lakehouse Sync Tables & Deployment Verification (Phase 4d)

After migration is complete and the app is reading/writing from Lakebase.

---

## Step 1 — Sync Table Check

Ask:

> "Now that your app is connected to Lakebase for reads and writes, one more thing:
>
> Has your Databricks admin set up any **sync tables** in Lakehouse that your app
> needs to read from? (These are curated tables in the Lakehouse that aggregate or
> transform your Lakebase data — commonly used for analytics, dashboards, or
> reporting features within the app.)
>
> If you're not sure, check with your workspace admin before proceeding."

**If user says yes:**

1. Ask which tables:
> "Which Lakehouse sync tables does your app need to read from?
> Please provide: catalog, schema, table names (e.g. `main.analytics.daily_order_summary`)"

2. Determine access method:

| Hosting | Sync Table Access Method |
|---|---|
| Databricks Apps | Databricks SQL via SDK (uses app service principal) |
| External (Vercel, AWS, etc.) | Databricks SQL via REST API or JDBC with PAT/M2M token |
| Backend script | Databricks SDK or `databricks-sql-connector` |

3. Generate the sync table reader:

**Python (databricks-sql-connector):**
```python
# db/lakehouse_reader.py
import os
from databricks import sql as databricks_sql

def get_lakehouse_conn():
    return databricks_sql.connect(
        server_hostname=os.environ["DATABRICKS_HOST"],
        http_path=os.environ["DATABRICKS_SQL_WAREHOUSE_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    )

ALLOWED_SYNC_TABLES = {"catalog.schema.table1", "catalog.schema.table2"}  # UPDATE

def read_sync_table(full_table_name: str, limit: int = 1000) -> list[dict]:
    if full_table_name not in ALLOWED_SYNC_TABLES:
        raise ValueError(f"Table '{full_table_name}' not in allowlist")
    with get_lakehouse_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM IDENTIFIER(%s) LIMIT %s", (full_table_name, limit))
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
```

**TypeScript (Databricks SQL REST API):**
```typescript
// lib/lakehouse-reader.ts
const DATABRICKS_HOST = process.env.DATABRICKS_HOST!
const DATABRICKS_TOKEN = process.env.DATABRICKS_TOKEN!
const WAREHOUSE_ID = process.env.DATABRICKS_SQL_WAREHOUSE_ID!

const ALLOWED_SYNC_TABLES = new Set(['catalog.schema.table1', 'catalog.schema.table2']) // UPDATE

export async function readSyncTable(fullTableName: string, limit = 1000): Promise<Record<string, unknown>[]> {
  if (!ALLOWED_SYNC_TABLES.has(fullTableName)) {
    throw new Error(`Table '${fullTableName}' not in allowlist`)
  }
  const res = await fetch(
    `${DATABRICKS_HOST}/api/2.0/sql/statements`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${DATABRICKS_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        warehouse_id: WAREHOUSE_ID,
        statement: `SELECT * FROM IDENTIFIER(:tableName) LIMIT :rowLimit`,
        parameters: [
          { name: 'tableName', value: fullTableName, type: 'STRING' },
          { name: 'rowLimit', value: String(limit), type: 'INT' },
        ],
        wait_timeout: '30s',
      }),
    }
  )
  const data = await res.json()
  if (data.status?.state !== 'SUCCEEDED') {
    throw new Error(`SQL statement ${data.status?.state}: ${data.status?.error?.message ?? 'unknown error'}`)
  }
  const cols = data.manifest.schema.columns.map((c: { name: string }) => c.name)
  return data.result.data_array.map((row: string[]) =>
    Object.fromEntries(cols.map((col: string, i: number) => [col, row[i]]))
  )
}
```

4. Add required environment variables:

```bash
DATABRICKS_HOST=<workspace>.cloud.databricks.com
DATABRICKS_TOKEN=<pat-or-m2m-token>
DATABRICKS_SQL_WAREHOUSE_PATH=/sql/1.0/warehouses/<warehouse-id>  # Python
DATABRICKS_SQL_WAREHOUSE_ID=<warehouse-id>                         # TypeScript REST
```

**If user says no or not sure:** Skip to Step 2.

---

## Step 2 — Web Deployment Verification

Ask:

> "Final check — have you:
>
> 1. **Pushed your code** to your web deployment?
> 2. **Updated your production environment variables?**
>    - Lakebase connection vars
>    - Sync table vars (if applicable)
>    - Removed old database vars from production config
>
> Both are needed for the migration to be live in production."

**If user confirms both:**

> "Please check your live app:
> 1. Test a **read** operation (load a list page — does data appear?)
> 2. Test a **write** operation (create/update a record — does it save?)
> 3. [If sync tables] Check analytics/dashboard features
>
> Is everything working?"

**If app is working:**

> "Migration fully deployed and verified. Your app is:
> - Reading/writing from **Lakebase** (OLTP)
> - [If sync tables] Reading analytics from **Lakehouse sync tables**
> - Data automatically syncs Lakebase → Lakehouse for your pipeline"

**If issues:** Diagnose based on symptom:
- Data not loading → check env vars, app restarted
- Write failing → check token permissions, connection string
- Sync tables empty → confirm admin ran sync job, warehouse running

**If not pushed/updated:**
- Help commit and push code if requested
- Guide to hosting platform's env var settings (Vercel, Databricks Apps, etc.)
