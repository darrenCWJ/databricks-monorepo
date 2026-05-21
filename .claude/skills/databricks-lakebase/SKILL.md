---
name: databricks-lakebase
description: >
  Unified Databricks/Lakebase integration skill. Handles the full lifecycle:
  codebase scanning, intent discovery, plan presentation, connection setup,
  security (PKCE + token rotation), and data access pattern generation.
  Supports all app types (frontend, fullstack, script, migration) and stacks
  (TypeScript, Python, Java/Kotlin).
  TRIGGER when: user mentions Databricks or Lakebase; DATABRICKS_HOST or
  Lakebase appears in config/env; .lakebase marker exists in project; user
  asks to connect, query, migrate, or integrate with Databricks; Databricks
  appears in ANY user answer during clarifying questions (e.g. selecting it
  as a data source, tech stack, or backend option) even if the original
  request did not mention Databricks.
  SKIP: user is working with a non-Databricks database only (Postgres, MySQL,
  MongoDB) with no Databricks involvement.
version: 1.0.0
tags: [databricks, lakebase, connection, security, data-access, architecture]
---

# Databricks Lakebase Skill

## Internal Router

Evaluate from top to bottom. Enter at the FIRST matching condition.

### Fast Path (Power Users)

If `.lakebase` exists AND the user explicitly requests specific output
(e.g. "give me psycopg3 connection code", "write queries for the orders table"):
- Read `.lakebase` for app_type/stack/personal
- Skip to the relevant phase (3, 4, or 5) directly
- Do NOT re-ask classification questions

### Re-entry (Mid-conversation)

If `.lakebase` exists AND connection + security files already exist AND user asks
for a new entity or query pattern:
- Determine connection type from existing files:
  - `lib/lakebase-client.ts` or `lib/api-client.ts` → Data API patterns
  - `db/connection.py` or `db/pool.ts` → PG wire patterns
- Enter at Phase 5 with matching query style

If `.lakebase` exists AND connection file exists but NO security layer:
- Enter at Phase 4

If `.lakebase` exists but NO connection file:
- Enter at Phase 3 (ask driver preference, then continue through 4-5)

### Transition Detection

If `.lakebase` says `frontend` but a backend entrypoint is being written:
- Re-run Phase 0-1 to reclassify
- Update `.lakebase`
- Continue from Phase 3

### First-time Setup

If NO `.lakebase` exists:
- Start at Phase 0

### Hook Context (Advisory Only)

The hook may pass context: `hostname_detected`, `keyword_intent`, `marker_exists`,
or `transition`. Use as a hint but ALWAYS verify actual file state in Phase 0.

---

## Phase 0 — Codebase Scan (Silent)

Scan the project WITHOUT asking questions. Check:

| Target | Signal |
|--------|--------|
| `.lakebase` | Existing marker — read app_type, stack, personal |
| `requirements.txt`, `pyproject.toml`, `package.json` | Stack detection |
| `main.py`, `app.py`, `server.ts`, `manage.py`, `Dockerfile` | App type |
| `.env`, `.env.local`, `.env.example` | Configured env vars, existing DB signals |
| ORM models, migration files, `DATABASE_URL` | Migration indicators |
| `lib/lakebase-client.ts`, `db/connection.py`, `db/pool.ts` | Existing connection |
| `auth/token-manager.ts`, `auth/token_rotator.py` | Existing security layer |
| `lib/api/*-queries.ts`, `db/queries/*.py` | Existing data patterns |

Produce internal state (do not show to user):

```
has_marker: bool
app_type: frontend | fullstack | script | migration | unknown
stack: typescript | python | java | kotlin | unknown
personal: bool | unknown
has_connection: bool
has_security: bool
has_data_patterns: list[str]
existing_db: string | null
env_vars_configured: list[str]
```

Use this state to determine which phases to skip.

---

## Phase 1 — Intent Discovery

Ask ONLY what cannot be determined from Phase 0. Maximum 2 questions.

### Question 1 — Intent (ask if no .lakebase AND intent unclear from message)

> "What would you like to do with Databricks/Lakebase?
> 1. **New integration** — connect a new or existing app to Lakebase
> 2. **Migrate** — move from another database (Postgres, MySQL, etc.) to Lakebase
> 3. **Add queries** — write data access code for tables (connection already exists)
> 4. **Fix/update** — fix a broken connection, update auth, or resolve an error"

- Answer 2 → ask **Migration Follow-up** (below), then route accordingly
- Answer 3 → jump to Phase 5
- Answer 4 → ask what's broken, provide targeted fix (no full pipeline)

### Migration Follow-up (ask only if Answer 2 selected)

> "How do you want to move your data to Lakebase?
> 1. **Start fresh** — no existing data to move, just create new tables
> 2. **Copy everything at once** — dump source, load into Lakebase, cutover
> 3. **Keep both running** — run old and new databases side by side
> 4. **Move table by table** — migrate one table at a time"

#### Follow-up for option 3 (ask only if "Keep both running" selected)

> "Which database will be your final destination?
> 1. **Lakebase** — sync from old → Lakebase, then drop old database
> 2. **Keep both permanently** — Lakebase as read replica for analytics"

**Routing:**

| Choice | What to generate | Also invoke |
|---|---|---|
| Start fresh | Schema creation scripts, `.env` setup | None |
| Copy everything | Export/import scripts, verification, cutover checklist | `database-migrations` |
| Keep both running | Sync strategy, replication pattern, cutover plan | `database-migrations` |
| Move table by table | Per-table migration plan, dual-read routing | `database-migrations` |

### Question 2 — Hosting (ask for ALL app types)

> "Where will this app be hosted?
> 1. **Databricks Apps** — hosted inside the Databricks workspace
> 2. **External** — hosted outside Databricks (Vercel, AWS, GCP, etc.)"

| Hosting | What happens next |
|---|---|
| Databricks Apps | Skip most of Phase 4 — platform auto-injects credentials |
| External | Ask **Question 2b — Audience** |

### Question 2b — Audience (ask only if hosting is External)

> "Do the app's end users have Databricks workspace accounts?
> 1. **Yes** — users authenticate directly with Databricks (internal tool)
> 2. **No** — users are external/public (e.g. customers)"

| Audience | Auth architecture |
|---|---|
| Yes (internal) | Frontend → Databricks OAuth PKCE → Data API directly |
| No (external) | Frontend → your auth → your backend → Data API via service principal |

### Question 3 — Workspace (ask if hosting is External)

> "Is this your personal Databricks workspace, or a shared team/org workspace?"

### Question 4 — Connection Method (ask for backend/fullstack/script if External)

Skip for frontend-only (always Data API) and migrations (always PG wire).

> "How should your backend connect to Lakebase?
> 1. **PostgreSQL direct (recommended)** — full SQL, transactions
> 2. **Data API (REST)** — simpler HTTP calls, basic CRUD only
> 3. **Not sure** — use PostgreSQL (can switch later)"

### After intent is clear:

Write `.lakebase` marker:

```json
{
  "app_type": "frontend|fullstack|backend|script",
  "intent": "new|migrate|queries|fix",
  "stack": "typescript|python|java|kotlin",
  "hosting": "databricks-apps|external",
  "audience": "internal|external|null",
  "personal": true|false|null,
  "connection_method": "data-api|pg-wire|both",
  "migration_type": "one-time|dual-run|gradual|null",
  "source_db": "postgres|mysql|sqlite|mongodb|null"
}
```

---

## Phase 2 — Plan Presentation

Present what will be generated. Wait for confirmation before writing any files.

> **Lakebase Integration Plan**
>
> | | |
> |---|---|
> | App type | [frontend / fullstack / script / migration] |
> | Hosting | [Databricks Apps / External] |
> | Audience | [internal / external] (external hosting only) |
> | Stack | [TypeScript / Python / Java / Kotlin] |
> | Auth | [Auto / PKCE / Backend proxy + SP / PAT / M2M] |
>
> **Files to generate:**
> 1. `[path]` — [purpose]
> ...
>
> **Env vars to configure:**
> - `VAR_NAME` — [where to find the value]
>
> **Shall I proceed?**

Do NOT generate files without confirmation.

---

## Phase 2b — Credential Onboarding (MANDATORY before code generation)

### Step 0 — Check for Credentials Template

Look for `lakebase-credentials.template` in the project root. If found:
1. Ensure both `lakebase-credentials.template` and `.env` are in `.gitignore`
2. Parse key=value pairs, merge into `.env` (overwrite only non-empty values)
3. Delete `lakebase-credentials.template` — must not persist
4. Report only which KEY NAMES were updated (e.g. "Merged: DATABRICKS_HOST,
   LAKEBASE_DATA_API_URL"). NEVER display, echo, or log credential values.
5. Continue to Step 1 to verify completeness

### Step 1 — Check Prerequisites

> "Before I generate code, do you already have:
> 1. A Databricks workspace?
> 2. A Lakebase project with tables?
> 3. The Data API enabled? (if using Data API)
> 4. A service principal or PAT configured?
> 5. Which **schema** are your tables in?
>
> Tip: If your admin gave you a `lakebase-credentials.template` file, drop it
> in your project root and I'll set everything up automatically."

If anything is missing → Read `references/credential-setup.md` for guided setup.

STOP if no workspace exists. Do NOT generate code without credentials configured.

---

## Phase 3 — Connection Setup

### Backend Driver Preference (ask 1 question for PG wire backends)

> "Which driver/ORM do you prefer?
> 1. **psycopg3** (recommended) — 2. psycopg2 — 3. asyncpg — 4. SQLAlchemy
> 5. Django ORM — 6. pg/node-postgres — 7. Prisma — 8. JDBC/HikariCP"

### Gotchas (apply to ALL PG wire connections)

- **`max_connections = 1`** — Lakebase uses OAuth tokens as passwords. Poolers
  reuse connections with stale tokens. Use 1 connection or fetch-per-request.
- **Scale-to-zero reconnection** — First connection after cold start may raise
  `OperationalError`. All connection code includes 3-attempt retry with 200ms backoff.

### Route to reference file:

| Hosting | Stack | Method | Read |
|---|---|---|---|
| Databricks Apps | any frontend | Data API | `references/connection-frontend.md` § "Databricks Apps" |
| External | TS frontend (internal users) | Data API + PKCE | `references/connection-frontend.md` § "External PKCE" |
| External | TS frontend (external users) | Backend proxy | `references/connection-frontend.md` § "Backend Proxy" |
| External | Python backend | PG wire | `references/connection-python.md` |
| External | TypeScript backend | PG wire | `references/connection-typescript.md` |
| External | Java/Kotlin | PG wire | `references/connection-java.md` |

Generate ONLY the chosen driver/ORM from the reference file.

---

## Phase 4 — Security Layer

### Route to reference file:

| Component | Condition | Read |
|---|---|---|
| PKCE login + token manager | Frontend with internal users (PKCE) | `references/security-frontend.md` |
| Backend token rotator | Any backend or script with PG wire | `references/security-backend.md` |
| Databricks Apps | Hosting = Databricks Apps | Skip — credentials auto-injected |

For Databricks Apps: no manual auth code needed. Platform injects
`DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET`. User tokens arrive
via `x-forwarded-access-token` header.

---

## Phase 4b — Data Migration (only if intent = migrate)

Read `references/data-migration.md` for the full migration workflow including:
- Source database detection and scope scan
- Path A (one-time copy), Path B (dual-run), Path C (gradual)
- Row count verification and live connection verification
- Cutover checklist

---

## Phase 4c — Post-Migration Cleanup (only if intent = migrate, after cutover)

Read `references/post-migration-cleanup.md` when the user confirms migration is
complete and ready to remove all references to the old database.

---

## Phase 4d — Deployment Verification (only if intent = migrate)

Read `references/deployment-verification.md` after all code changes are complete
to handle sync table connections and production deployment confirmation.

---

## Phase 5 — Data Patterns

### Route by Connection Method

Check `.lakebase` for `connection_method` and `hosting`:

| connection_method | hosting | Read |
|---|---|---|
| `data-api` | any | `references/data-patterns-frontend.md` |
| `pg-wire` | any (Python) | `references/data-patterns-backend.md` |
| `pg-wire` | any (TypeScript) | Use connection from Phase 3 with raw SQL queries |
| not set | — | Check existing files to determine, or ask |

### Step 1 — Discover Entities

Scan for existing schema files, models, or migrations. If nothing found, ask:

> "What are the main tables in your Lakebase project?
> List them with key columns, e.g.:
> - users (id, name, email, created_at)
> - orders (id, user_id, total, status)"

### Step 2 — Required Operations

> "For each entity, which operations?
> 1. Read-only (list + get by ID)
> 2. Full CRUD
> 3. Bulk insert
> 4. Multi-table transactions
> 5. Specific queries (describe)"

### Step 3 — Generate Query Files

Load the appropriate reference file and generate query modules for each entity.

---

## Phase 6 — Verification

### Test Script

Generate a connection verification script for the user's stack:

**Python:** `scripts/verify_lakebase.py` — connects, runs `SELECT version()`, prints success.
**TypeScript:** `scripts/test-connection.ts` — calls Data API, confirms reachable.

### Security Checklist

- [ ] No tokens or passwords committed to source control
- [ ] `.env` in `.gitignore`
- [ ] `.env.example` created with placeholders
- [ ] SSL enforced (`sslmode=require`)
- [ ] Credentials loaded from env vars only
- [ ] No connection poolers with OAuth connections
- [ ] Token rotation implemented (backend) or silent refresh (frontend)
- [ ] Tokens in `sessionStorage` only (frontend — never `localStorage`)

### Completion Summary

> "Lakebase integration complete.
>
> **Files created:** [list]
> **Test:** `[run command]`
>
> All layers in place: connection → security → data access.
> Need help wiring these into your routes or components?"
