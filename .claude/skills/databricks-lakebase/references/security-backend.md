# Backend Security — Token Rotator & Credential Management

## How Token Rotation Works

```
Auth credential (PAT or M2M secret)
  → WorkspaceClient authenticates to Databricks API
    → generate_database_credential(endpoint=...)
      → short-lived Lakebase token (~1 hour)
        → used as psycopg / pg password
```

## Auth Modes

| Mode | Env vars | Best for |
|---|---|---|
| Static token | `LAKEBASE_OAUTH_TOKEN` | Quick local testing only (~1h expiry) |
| PAT auto-rotate | `DATABRICKS_HOST` + `DATABRICKS_TOKEN` | Personal workspace |
| M2M auto-rotate | `DATABRICKS_HOST` + `DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET` | Team workspace |

---

## Python — Token Rotator

```python
# auth/token_rotator.py
import logging
import os
import time
import threading

logger = logging.getLogger(__name__)

_REFRESH_BUFFER = 60


class LakebaseTokenRotator:
    def __init__(self) -> None:
        from databricks.sdk import WorkspaceClient
        self._client = WorkspaceClient()
        self._endpoint = os.environ["LAKEBASE_ENDPOINT_PATH"]
        self._token: str | None = None
        self._expiry: float = 0.0
        self._lock = threading.Lock()

    def get_token(self) -> str:
        with self._lock:
            if time.time() >= self._expiry - _REFRESH_BUFFER:
                self._refresh()
            token = self._token
        if token is None:
            raise RuntimeError("Lakebase token not available — check credentials")
        return token

    def _refresh(self) -> None:
        cred = self._client.postgres.generate_database_credential(
            endpoint=self._endpoint
        )
        self._token = cred.token
        try:
            if cred.expire_time and hasattr(cred.expire_time, 'timestamp'):
                self._expiry = cred.expire_time.timestamp()
            elif cred.expire_time:
                self._expiry = float(cred.expire_time)
            else:
                self._expiry = time.time() + 3600
        except (TypeError, ValueError):
            self._expiry = time.time() + 3600


_rotator: LakebaseTokenRotator | None = None
_rotator_lock = threading.Lock()


def _sdk_credentials_configured() -> bool:
    has_pat = bool(os.environ.get("DATABRICKS_TOKEN"))
    has_m2m = bool(
        os.environ.get("DATABRICKS_CLIENT_ID")
        and os.environ.get("DATABRICKS_CLIENT_SECRET")
    )
    return has_pat or has_m2m


def get_lakebase_token() -> str:
    if _sdk_credentials_configured():
        global _rotator
        if _rotator is None:
            with _rotator_lock:
                if _rotator is None:
                    _rotator = LakebaseTokenRotator()
        return _rotator.get_token()

    token = os.environ.get("LAKEBASE_OAUTH_TOKEN", "")
    if not token:
        raise RuntimeError(
            "No Lakebase credentials found. Set either:\n"
            "  DATABRICKS_TOKEN=<pat>          (auto-rotation, dev)\n"
            "  DATABRICKS_CLIENT_ID + SECRET   (auto-rotation, production)\n"
            "  LAKEBASE_OAUTH_TOKEN=<token>    (static, expires ~1h, testing only)"
        )
    logger.warning(
        "Using static LAKEBASE_OAUTH_TOKEN — expires ~1 hour. "
        "Set DATABRICKS_TOKEN for automatic rotation."
    )
    return token
```

---

## Node.js — Token Rotator

```typescript
// auth/token-rotator.ts
import { WorkspaceClient } from '@databricks/sdk'

let cachedToken: string | null = null
let tokenExpiry = 0
let refreshPromise: Promise<string> | null = null
const REFRESH_BUFFER = 60_000

export async function getLakebaseToken(): Promise<string> {
  if (cachedToken && Date.now() < tokenExpiry - REFRESH_BUFFER) {
    return cachedToken
  }
  if (refreshPromise) return refreshPromise
  refreshPromise = (async () => {
    try {
      const client = new WorkspaceClient()
      const cred = await client.postgres.generateDatabaseCredential({
        endpoint: process.env.LAKEBASE_ENDPOINT_PATH!,
      })
      cachedToken = cred.token
      tokenExpiry = cred.expireTime
        ? new Date(cred.expireTime).getTime()
        : Date.now() + 3_600_000
      return cachedToken!
    } finally {
      refreshPromise = null
    }
  })()
  return refreshPromise
}
```

---

## Credential Navigation

**Frontend path — Data API URL + OAuth App:**

1. Log in to Databricks workspace
2. Navigate to **Lakebase** → select project → **Data API** tab
3. Click **Enable Data API** (if not already enabled)
4. Copy the **REST endpoint URL** (this is your `VITE_DATA_API_BASE_URL`)
5. Configure **CORS** in Advanced Settings: add your app's domain
6. Register OAuth application:
   - If personal workspace: Workspace Settings → Security → OAuth Applications → Add
   - If team workspace: share instructions with admin

**Admin request template (team workspace):**

> "Please register an OAuth application in Workspace Settings → Security → OAuth Applications:
> - Name: `your-app-name`
> - Redirect URIs: `http://localhost:5173/auth/callback` (add production URI too)
> - Grant types: `Authorization Code`
> - Return the **Client ID** — no client secret needed for PKCE."

**Backend path — PostgreSQL connection + SDK credentials:**

1. Lakebase Postgres → select project → **Connect** (top-right)
2. Configure: Branch, Compute, Database, Role
3. Copy: Host, Database, User, Endpoint path

**SDK credential choice (based on `.lakebase` personal field):**

| Context | Recommended | Why |
|---|---|---|
| Personal workspace | PAT | You own the account — departure risk is zero |
| Team/org workspace | M2M service principal | PAT tied to personal account breaks if you leave |

**PAT setup:** User Settings → Developer → Access tokens → scope: **`postgres`** (not `sql`)

**M2M setup (personal workspace):** Settings → Identity & Access → Service principals → Add → Generate secret → Assign `Can use` on Lakebase project

**M2M setup (team workspace — share with admin):**

> "Please create a service principal for Lakebase access:
> 1. Settings → Identity & Access → Service principals → Add (name: `yourapp-lakebase-prod`)
> 2. Generate secret (shown once — save immediately)
> 3. Assign `Can use` on the Lakebase project
> 4. Return Client ID + Client Secret to developer."

---

## Backend env vars

```env
DATABRICKS_HOST=https://your-workspace.databricks.com
DATABRICKS_TOKEN=<PAT>                       # personal / dev
# OR for team:
DATABRICKS_CLIENT_ID=<service principal ID>
DATABRICKS_CLIENT_SECRET=<service principal secret>

LAKEBASE_HOST=ep-abc-123.databricks.com
LAKEBASE_PORT=5432
LAKEBASE_DB=databricks_postgres
LAKEBASE_USER=your_role_name
LAKEBASE_ENDPOINT_PATH=projects/my-project/branches/production/endpoints/primary
DATABASE_URL=postgresql://your_role_name@ep-abc-123.databricks.com/databricks_postgres?sslmode=require
```

---

## Secret Management

- Never commit `.env` — add to `.gitignore`
- Always create `.env.example` with placeholders
- Load credentials from environment variables at runtime

```env
# .env.example — commit this
DATABRICKS_HOST=https://your-workspace.databricks.com
DATABRICKS_TOKEN=                    # dev: personal access token (postgres scope)
DATABRICKS_CLIENT_ID=                # prod: service principal
DATABRICKS_CLIENT_SECRET=            # prod: service principal secret
LAKEBASE_HOST=
LAKEBASE_PORT=5432
LAKEBASE_DB=
LAKEBASE_USER=
LAKEBASE_ENDPOINT_PATH=projects/.../branches/.../endpoints/primary
DATABASE_URL=                        # postgresql://user@host/db?sslmode=require
```
