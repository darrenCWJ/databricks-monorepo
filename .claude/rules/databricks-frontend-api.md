---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
---
# Databricks Frontend Patterns

> Frontend-only apps must use the Lakebase Data API — never direct Databricks connections.
> Extends [common/patterns.md](../common/patterns.md).

## Architecture

```
Frontend → Data API (PostgREST) ← OIDC OAuth token ← Lakebase Postgres
```

## Rules

- NEVER connect to Databricks directly from frontend — use Data API only
- NEVER use hardcoded PAT tokens — use OIDC OAuth flow only
- NEVER store tokens in `localStorage` — memory or `sessionStorage` only
- NEVER write SQL strings in frontend — use PostgREST filter operators
- ALWAYS read Data API base URL from env (`VITE_DATA_API_BASE_URL`)
- ALWAYS filter PATCH and DELETE requests — never unguarded bulk mutations

## Reference

See skill: `databricks-lakebase` for Data API client, OIDC token manager, and query patterns.
