# Frontend Security — PKCE Login & Token Management

## PKCE Login Flow

```typescript
// auth/pkce.ts
function generateCodeVerifier(): string {
  const array = new Uint8Array(32)
  crypto.getRandomValues(array)
  return btoa(String.fromCharCode(...array))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
}

async function generateCodeChallenge(verifier: string): Promise<string> {
  const data = new TextEncoder().encode(verifier)
  const digest = await crypto.subtle.digest('SHA-256', data)
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
}

export async function initiateLogin(): Promise<void> {
  const verifier = generateCodeVerifier()
  const challenge = await generateCodeChallenge(verifier)
  const state = crypto.randomUUID()

  sessionStorage.setItem('pkce_verifier', verifier)
  sessionStorage.setItem('oauth_state', state)

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: import.meta.env.VITE_DATABRICKS_CLIENT_ID,
    redirect_uri: import.meta.env.VITE_OAUTH_REDIRECT_URI,
    scope: 'offline_access all-apis',
    code_challenge: challenge,
    code_challenge_method: 'S256',
    state,
  })

  window.location.href =
    `${import.meta.env.VITE_DATABRICKS_HOST}/oidc/v1/authorize?${params}`
}

export async function handleCallback(
  code: string,
  returnedState: string
): Promise<void> {
  const verifier = sessionStorage.getItem('pkce_verifier')
  const expectedState = sessionStorage.getItem('oauth_state')

  if (!verifier) throw new Error('PKCE verifier missing — possible CSRF')
  if (returnedState !== expectedState) throw new Error('OAuth state mismatch — possible CSRF')

  const res = await fetch(
    `${import.meta.env.VITE_DATABRICKS_HOST}/oidc/v1/token`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        code,
        redirect_uri: import.meta.env.VITE_OAUTH_REDIRECT_URI,
        client_id: import.meta.env.VITE_DATABRICKS_CLIENT_ID,
        code_verifier: verifier,
      }),
    }
  )
  if (!res.ok) throw new Error(`Token exchange failed: ${res.status}`)

  sessionStorage.removeItem('pkce_verifier')
  sessionStorage.removeItem('oauth_state')

  const { access_token, refresh_token, expires_in } = await res.json()
  sessionStorage.setItem(
    'databricks_tokens',
    JSON.stringify({
      accessToken: access_token,
      refreshToken: refresh_token,
      expiresAt: Date.now() + expires_in * 1000,
    })
  )
}
```

**Callback route** — create a page at `/auth/callback`:
```typescript
const params = new URLSearchParams(window.location.search)

if (params.has('error')) {
  const error = params.get('error')
  const description = params.get('error_description') ?? 'Unknown error'
  throw new Error(`OAuth error: ${error} — ${description}`)
}

const code = params.get('code')
const state = params.get('state')
if (!code || !state) {
  throw new Error('Missing code or state in OAuth callback')
}
await handleCallback(code, state)
```

---

## Silent Refresh (Token Manager)

Tokens expire in ~1 hour. Rules:
- Store in `sessionStorage` only — never `localStorage`
- Deduplicate concurrent refresh calls
- On failure, clear tokens and redirect to login

```typescript
// auth/token-manager.ts
interface TokenState {
  accessToken: string
  refreshToken: string
  expiresAt: number
}

class DatabricksTokenManager {
  private refreshPromise: Promise<string> | null = null

  private getState(): TokenState | null {
    const raw = sessionStorage.getItem('databricks_tokens')
    return raw ? (JSON.parse(raw) as TokenState) : null
  }

  private setState(state: TokenState): void {
    sessionStorage.setItem('databricks_tokens', JSON.stringify(state))
  }

  async getAccessToken(): Promise<string> {
    const state = this.getState()
    if (!state) throw new Error('Not authenticated. Please log in.')
    if (Date.now() >= state.expiresAt - 60_000) {
      return this.silentRefresh(state.refreshToken)
    }
    return state.accessToken
  }

  private silentRefresh(refreshToken: string): Promise<string> {
    if (!this.refreshPromise) {
      this.refreshPromise = this.doRefresh(refreshToken).finally(() => {
        this.refreshPromise = null
      })
    }
    return this.refreshPromise
  }

  private async doRefresh(refreshToken: string): Promise<string> {
    const res = await fetch(
      `${import.meta.env.VITE_DATABRICKS_HOST}/oidc/v1/token`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          grant_type: 'refresh_token',
          refresh_token: refreshToken,
          client_id: import.meta.env.VITE_DATABRICKS_CLIENT_ID,
        }),
      }
    )
    if (!res.ok) {
      this.clearTokens()
      throw new Error('Session expired. Please log in again.')
    }
    const { access_token, refresh_token: newRefreshToken, expires_in } =
      await res.json()
    this.setState({
      accessToken: access_token,
      refreshToken: newRefreshToken ?? refreshToken,
      expiresAt: Date.now() + expires_in * 1000,
    })
    return access_token
  }

  isAuthenticated(): boolean {
    return this.getState() !== null
  }

  clearTokens(): void {
    sessionStorage.removeItem('databricks_tokens')
  }
}

export const tokenManager = new DatabricksTokenManager()
```

---

## Frontend env vars

```env
VITE_DATABRICKS_HOST=https://your-workspace.databricks.com
VITE_DATABRICKS_CLIENT_ID=<from OAuth app>
VITE_OAUTH_REDIRECT_URI=http://localhost:5173/auth/callback
VITE_DATA_API_BASE_URL=<REST endpoint URL from Lakebase project → Data API tab>
```
