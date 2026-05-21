# TypeScript Backend Connection Templates (PG Wire)

All TypeScript backends connect via PostgreSQL wire protocol with OAuth token rotation.
The `getLakebaseToken()` function comes from `references/security-backend.md`.

---

## pg / node-postgres

```typescript
// db/pool.ts
import { Pool } from 'pg'
import { getLakebaseToken } from '@/auth/token-rotator'

export function createPool() {
  return new Pool({
    host: process.env.LAKEBASE_HOST,
    port: Number(process.env.LAKEBASE_PORT ?? 5432),
    database: process.env.LAKEBASE_DB,
    user: process.env.LAKEBASE_USER,
    password: () => getLakebaseToken(),
    ssl: { rejectUnauthorized: true },
    max: 1,
  })
}
```

---

## Prisma

```typescript
// db/prisma.ts
import { PrismaClient } from '@prisma/client'
import { getLakebaseToken } from '@/auth/token-rotator'

async function buildDatabaseUrl(): Promise<string> {
  const token = encodeURIComponent(await getLakebaseToken())
  const host = process.env.LAKEBASE_HOST
  const db = process.env.LAKEBASE_DB
  const user = process.env.LAKEBASE_USER
  return `postgresql://${user}:${token}@${host}:5432/${db}?sslmode=require`
}

export async function getPrismaClient(): Promise<PrismaClient> {
  const url = await buildDatabaseUrl()
  return new PrismaClient({
    datasources: { db: { url } },
  })
}

let _prisma: PrismaClient | null = null
let _prismaExpiry = 0
let _refreshing: Promise<PrismaClient> | null = null

export async function getPersistentPrismaClient(): Promise<PrismaClient> {
  if (_prisma && Date.now() <= _prismaExpiry) {
    return _prisma
  }
  if (_refreshing) return _refreshing
  _refreshing = (async () => {
    try {
      if (_prisma) await _prisma.$disconnect()
      _prisma = await getPrismaClient()
      _prismaExpiry = Date.now() + 45 * 60 * 1000
      return _prisma
    } finally {
      _refreshing = null
    }
  })()
  return _refreshing
}
```
