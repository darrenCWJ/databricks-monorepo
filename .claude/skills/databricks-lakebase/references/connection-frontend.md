# Frontend Connection Templates

## Databricks Apps (Auto-Auth)

No manual auth code needed. Databricks auto-injects credentials and forwards user tokens.

```typescript
// lib/lakebase-client.ts
// In Databricks Apps, user token arrives via x-forwarded-access-token header.

const DATA_API_BASE = process.env.LAKEBASE_DATA_API_URL
const SCHEMA = process.env.LAKEBASE_SCHEMA ?? 'public'

export async function dataApiFetch<T>(
  path: string,
  userToken: string,
  params?: Record<string, string>
): Promise<T> {
  const url = new URL(`${DATA_API_BASE}/${SCHEMA}/${path}`)
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
  const res = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${userToken}` },
  })
  if (!res.ok) throw new Error(`Data API ${res.status}: ${await res.text()}`)
  return res.json() as Promise<T>
}

// In your request handler, extract the forwarded token:
// const userToken = req.headers['x-forwarded-access-token']
// const data = await dataApiFetch('users', userToken)
```

**Env vars (auto-injected by Databricks Apps — no manual setup):**
- `DATABRICKS_CLIENT_ID` — service principal client ID (for app-level operations)
- `DATABRICKS_CLIENT_SECRET` — service principal secret (for app-level operations)

**For user-level operations:** Extract `x-forwarded-access-token` from incoming request headers and pass it to the Data API. This preserves the user's identity for RLS policies.

**For app-level operations (background tasks, shared data):** Use the auto-injected service principal credentials with the token rotator pattern from Phase 4.

---

## External Hosting + Internal Users (Direct Data API via PKCE)

No PostgreSQL driver needed. Auth via Databricks OAuth PKCE.
Users must have Databricks workspace accounts.

> `tokenManager` is generated in Phase 4 — this file will have unresolved imports
> until the security phase completes.

```typescript
// lib/lakebase-client.ts
import { tokenManager } from '@/auth/token-manager'

const DATA_API_BASE = import.meta.env.VITE_DATA_API_BASE_URL

export async function dataApiFetch<T>(
  path: string,
  params?: Record<string, string>
): Promise<T> {
  const token = await tokenManager.getAccessToken()
  const url = new URL(`${DATA_API_BASE}/${path}`)
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
  const res = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(`Data API ${res.status}: ${await res.text()}`)
  return res.json() as Promise<T>
}

export async function dataApiMutate<T>(
  path: string,
  method: 'POST' | 'PATCH' | 'DELETE',
  body?: unknown,
  prefer?: string
): Promise<T> {
  const token = await tokenManager.getAccessToken()
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }
  if (prefer) headers['Prefer'] = prefer
  const res = await fetch(`${DATA_API_BASE}/${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`Data API ${method} ${res.status}: ${await res.text()}`)
  return res.status === 204 ? (undefined as T) : (res.json() as Promise<T>)
}
```

---

## External App — Backend Proxy (external users without Databricks accounts)

For apps where end users do NOT have Databricks accounts. The frontend uses your
own auth system; a thin backend proxies Data API calls using a service principal.

```
User → Your Auth (Google, email, etc.) → Your Backend → Lakebase Data API
                                              ↓
                                    Service principal OAuth token
```

**Frontend client (calls YOUR backend, not Data API directly):**

```typescript
// lib/api-client.ts
const API_BASE = import.meta.env.VITE_API_BASE_URL // your backend

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/${path}`, {
    ...options,
    headers: {
      ...options?.headers,
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getSessionToken()}`, // YOUR app's auth token
    },
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`)
  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body: unknown) =>
    apiFetch<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    apiFetch<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: 'DELETE' }),
}
```

**Backend proxy (Python/FastAPI example):**

```python
# api/lakebase_proxy.py
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from auth.dependencies import get_current_user  # YOUR auth
from auth.databricks_oauth import get_databricks_oauth_token

router = APIRouter(prefix="/api/data")

DATA_API_BASE = os.environ["LAKEBASE_DATA_API_URL"]
SCHEMA = os.environ.get("LAKEBASE_SCHEMA", "public")

ALLOWED_TABLES: set[str] = {"users", "orders", "products"}  # UPDATE with your tables

def _validate_table(table: str) -> str:
    if table not in ALLOWED_TABLES:
        raise HTTPException(status_code=403, detail=f"Table '{table}' not allowed")
    return table

async def proxy_to_data_api(
    method: str,
    path: str,
    params: dict | None = None,
    body: dict | None = None,
):
    token = get_databricks_oauth_token()
    async with httpx.AsyncClient() as client:
        res = await client.request(
            method,
            f"{DATA_API_BASE}/{SCHEMA}/{path}",
            params=params,
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
    if not res.is_success:
        raise HTTPException(status_code=res.status_code, detail=res.text)
    return res.json() if res.content else None

@router.get("/{table}")
async def list_rows(table: str, user=Depends(get_current_user)):
    return await proxy_to_data_api("GET", _validate_table(table))

@router.post("/{table}")
async def create_row(table: str, body: dict, user=Depends(get_current_user)):
    return await proxy_to_data_api("POST", _validate_table(table), body=body)

@router.patch("/{table}")
async def update_row(table: str, body: dict, id: int, user=Depends(get_current_user)):
    t = _validate_table(table)
    return await proxy_to_data_api("PATCH", f"{t}?id=eq.{id}", body=body)

@router.delete("/{table}")
async def delete_row(table: str, id: int, user=Depends(get_current_user)):
    t = _validate_table(table)
    return await proxy_to_data_api("DELETE", f"{t}?id=eq.{id}")
```

**Databricks OAuth token helper (for Data API — NOT the PG credential rotator):**

```python
# auth/databricks_oauth.py
import os
import time
import threading
from databricks.sdk import WorkspaceClient

_token: str | None = None
_expiry: float = 0.0
_lock = threading.Lock()

def get_databricks_oauth_token() -> str:
    """Get a Databricks OAuth token for Data API calls.
    Uses service principal credentials (DATABRICKS_CLIENT_ID + SECRET).
    This is different from generate_database_credential which is for PG wire protocol."""
    global _token, _expiry
    with _lock:
        if time.time() >= _expiry - 60:
            client = WorkspaceClient(
                host=os.environ["DATABRICKS_HOST"],
                client_id=os.environ["DATABRICKS_CLIENT_ID"],
                client_secret=os.environ["DATABRICKS_CLIENT_SECRET"],
            )
            headers_fn = client.config.authenticate
            auth_header = headers_fn().get("Authorization", "")
            token_value = auth_header.removeprefix("Bearer ")
            if not token_value:
                raise RuntimeError("Failed to obtain OAuth token from Databricks SDK")
            _token = token_value
            _expiry = time.time() + 3600
        result = _token
    if result is None:
        raise RuntimeError("OAuth token not available")
    return result
```

**Backend proxy (TypeScript/Express example):**

```typescript
// routes/data-proxy.ts
import { Router } from 'express'
import { getDatabricksOAuthToken } from '@/auth/databricks-oauth'
import { requireAuth } from '@/middleware/auth' // YOUR auth middleware

const router = Router()
const DATA_API_BASE = process.env.LAKEBASE_DATA_API_URL!
const SCHEMA = process.env.LAKEBASE_SCHEMA ?? 'public'

const ALLOWED_TABLES = new Set(['users', 'orders', 'products']) // UPDATE
const POSTGREST_OPERATORS = /^(eq|neq|gt|gte|lt|lte|like|ilike|is|in|not)\./
const MAX_LIMIT = 100

const TABLE_COLUMNS: Record<string, Set<string>> = {
  users: new Set(['id', 'email', 'name', 'created_at']),
  orders: new Set(['id', 'user_id', 'status', 'total', 'created_at']),
  products: new Set(['id', 'name', 'price', 'category']),
} // UPDATE with your actual columns

function validateTable(table: string): string {
  if (!ALLOWED_TABLES.has(table)) throw new Error(`Table '${table}' not allowed`)
  return table
}

function validateSelect(table: string, select: string): string {
  const cols = select.split(',').map(s => s.trim())
  const allowed = TABLE_COLUMNS[table] ?? new Set()
  for (const col of cols) {
    if (col.includes('(')) throw new Error('Resource embedding not allowed')
    if (!allowed.has(col) && col !== '*') throw new Error(`Column '${col}' not allowed`)
  }
  return select
}

function filterQueryParams(table: string, query: Record<string, any>): URLSearchParams {
  const params = new URLSearchParams()
  const allowed = TABLE_COLUMNS[table] ?? new Set()
  for (const [key, value] of Object.entries(query)) {
    const strValue = String(value)
    if (key === 'select') {
      params.set(key, validateSelect(table, strValue))
    } else if (key === 'order') {
      const col = strValue.replace(/\.(asc|desc)$/, '')
      if (allowed.has(col)) params.set(key, strValue)
    } else if (key === 'limit') {
      params.set(key, String(Math.min(Number(strValue) || MAX_LIMIT, MAX_LIMIT)))
    } else if (key === 'offset') {
      params.set(key, String(Math.max(0, Number(strValue) || 0)))
    } else if (allowed.has(key) && POSTGREST_OPERATORS.test(strValue)) {
      params.set(key, strValue)
    }
  }
  return params
}

async function proxyToDataApi(method: string, path: string, body?: unknown) {
  const token = await getDatabricksOAuthToken()
  const res = await fetch(`${DATA_API_BASE}/${SCHEMA}/${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`Data API ${res.status}: ${await res.text()}`)
  return res.status === 204 ? null : res.json()
}

router.get('/:table', requireAuth, async (req, res) => {
  const table = validateTable(req.params.table)
  const params = filterQueryParams(table, req.query as Record<string, any>)
  const data = await proxyToDataApi('GET', `${table}?${params}`)
  res.json(data)
})

router.post('/:table', requireAuth, async (req, res) => {
  const data = await proxyToDataApi('POST', validateTable(req.params.table), req.body)
  res.json(data)
})

export default router
```

**Env vars for external app using Data API:**

```env
LAKEBASE_DATA_API_URL=<REST endpoint URL from Lakebase project → Data API tab>
DATABRICKS_HOST=https://your-workspace.databricks.com
DATABRICKS_CLIENT_ID=<service principal ID>
DATABRICKS_CLIENT_SECRET=<service principal secret>
```

> Note: `LAKEBASE_ENDPOINT_PATH` is NOT needed for Data API — that's only for
> PostgreSQL wire protocol connections. The Data API uses standard Databricks
> OAuth tokens obtained via the SDK's `WorkspaceClient`.

> The service principal needs a Postgres role created via
> `SELECT databricks_create_role('<service-principal-application-id>', 'SERVICE_PRINCIPAL');`
> and appropriate GRANT statements on the tables.
