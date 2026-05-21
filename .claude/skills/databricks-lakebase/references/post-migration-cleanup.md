# Post-Migration Code Cleanup (Phase 4c)

**When to run this phase:**
- **One-time copy:** Run immediately after data is verified and app is switched over
- **Dual-run:** Run ONLY after the user confirms full cutover to Lakebase
- **Gradual migration:** Run ONLY after ALL tables are migrated and user confirms cutover

Ask before proceeding:
> "Has the migration fully completed? Are you ready to remove all references to the old database?"

---

## Step 1 — Scan for Legacy References

Search the codebase for any remaining references to the old database:

```bash
grep -rn "SOURCE_DATABASE_URL\|OLD_DB_\|legacy.*conn\|old.*pool" --include="*.{py,ts,tsx,js,jsx,env*,yml,yaml,json,toml}" .
grep -rn "psycopg2\|mysql\|sqlite3\|mongoose" --include="*.{py,ts,js}" .
grep -rn "localhost:5432\|localhost:3306\|127.0.0.1:5432" .
```

Check for:
- [ ] Old `DATABASE_URL` or source connection env vars
- [ ] Old driver imports (`psycopg2`, `mysql-connector`, `sqlite3`, `mongoose`)
- [ ] Old connection pool files (`db/old_pool.ts`, `db/legacy_connection.py`)
- [ ] Dual-read router code (if gradual migration was used)
- [ ] Dual-write middleware
- [ ] Old migration tool config (`alembic.ini` pointing to old DB)
- [ ] Docker compose services for the old database
- [ ] CI/CD scripts that provision or test against the old DB
- [ ] Hardcoded connection strings in test fixtures

## Step 2 — Replace Old Connections

| What | Action |
|---|---|
| Old driver imports | Replace with Lakebase connection import |
| `SOURCE_DATABASE_URL` env var | Remove from `.env`, `.env.example`, CI config |
| Old connection files | Delete (e.g. `db/postgres_pool.py`, `db/mysql.ts`) |
| Dual-read router | Replace with direct Lakebase calls |
| Dual-write middleware | Remove entirely |
| Docker compose DB service | Remove old `postgres:` or `mysql:` service |
| Old ORM config | Update to point to Lakebase (or remove if using Data API) |

## Step 3 — Remove Old Dependencies

```bash
# Python — remove old drivers no longer needed
pip uninstall psycopg2 mysql-connector-python pymongo

# Node — remove old drivers
npm uninstall pg mysql2 mongoose better-sqlite3
# Keep pg if still using it for Lakebase wire protocol
```

Only remove drivers that are fully replaced.

## Step 4 — Update Configuration Files

- [ ] `.env.example` — remove old vars, ensure only Lakebase vars remain
- [ ] `docker-compose.yml` — remove old DB service, volumes, networks
- [ ] CI/CD pipeline — remove old DB provisioning steps
- [ ] ORM schema — update `datasource` URL to Lakebase
- [ ] Health check endpoints — update to check Lakebase, not old DB

## Step 5 — Verify No Orphaned References

```bash
# Final grep — should return ZERO results
grep -rn "SOURCE_DATABASE_URL\|OLD_DB_" --include="*.{py,ts,tsx,js,jsx}" .
```

## Step 6 — Cleanup Checklist

- [ ] All code imports use Lakebase connection modules
- [ ] No env vars reference the old database
- [ ] Old driver packages removed from dependencies
- [ ] Docker compose has no old DB services
- [ ] CI/CD provisions Lakebase (or Data API), not old DB
- [ ] Tests pass without old database running
- [ ] `.lakebase` marker updated: remove `source_db` field
- [ ] Old database kept read-only for rollback window (7-14 days)
- [ ] After rollback window: decommission old database
