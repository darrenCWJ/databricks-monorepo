# Frontend Data Patterns — TypeScript Query Modules (Data API)

## Databricks Apps Variant

Same patterns as below, but token comes from request header instead of token manager:

```typescript
// lib/lakebase-client.ts (Databricks Apps)
const DATA_API_BASE = process.env.LAKEBASE_DATA_API_URL
const SCHEMA = process.env.LAKEBASE_SCHEMA ?? 'public'

export async function dataApiFetch<T>(
  path: string,
  userToken: string,  // from x-forwarded-access-token header
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
```

---

## Query Module Template

For each entity, generate `lib/api/[entity]-queries.ts` and `types/[entity].ts`.

```typescript
// types/[entity].ts
export interface [Entity] {
  id: number
  [column]: [type]
}
```

```typescript
// lib/api/[entity]-queries.ts
import { dataApiFetch, dataApiMutate } from '@/lib/lakebase-client'
import type { [Entity] } from '@/types/[entity]'

export async function getAll[Entities](filters?: {
  limit?: number
  afterId?: number
}): Promise<[Entity][]> {
  const params: Record<string, string> = {
    select: 'id,[columns]',
    order: 'id.asc',
    limit: String(filters?.limit ?? 20),
  }
  if (filters?.afterId) params['id'] = `gt.${filters.afterId}`
  return dataApiFetch<[Entity][]>('[entity]', params)
}

export async function get[Entity]ById(id: number): Promise<[Entity] | null> {
  const rows = await dataApiFetch<[Entity][]>('[entity]', {
    id: `eq.${id}`,
    limit: '1',
  })
  return rows[0] ?? null
}

export async function create[Entity](data: Omit<[Entity], 'id'>): Promise<[Entity]> {
  const [created] = await dataApiMutate<[Entity][]>(
    '[entity]',
    'POST',
    data,
    'return=representation'
  )
  return created
}

export async function update[Entity](
  id: number,
  data: Partial<Omit<[Entity], 'id'>>
): Promise<void> {
  await dataApiMutate('[entity]?id=eq.' + id, 'PATCH', data)
}

export async function delete[Entity](id: number): Promise<void> {
  await dataApiMutate('[entity]?id=eq.' + id, 'DELETE')
}
```

**Bulk insert:**
```typescript
export async function bulkCreate[Entities](
  items: Omit<[Entity], 'id'>[]
): Promise<[Entity][]> {
  return dataApiMutate<[Entity][]>(
    '[entity]',
    'POST',
    items,
    'return=representation'
  )
}
```

---

## PostgREST Filter Operators

| Operator | Meaning | Example |
|---|---|---|
| `eq.value` | = | `status: 'eq.active'` |
| `neq.value` | != | `status: 'neq.deleted'` |
| `gt.value` | > | `id: 'gt.100'` |
| `gte.value` | >= | `created_at: 'gte.2024-01-01'` |
| `lt.value` | < | `price: 'lt.50'` |
| `lte.value` | <= | `score: 'lte.100'` |
| `like.*term*` | LIKE | `name: 'like.*john*'` |
| `ilike.*term*` | ILIKE | `email: 'ilike.*@gmail*'` |
| `in.(a,b,c)` | IN | `status: 'in.(active,pending)'` |
| `is.null` | IS NULL | `deleted_at: 'is.null'` |
| `not.is.null` | IS NOT NULL | `email: 'not.is.null'` |

---

## Error Handling

```typescript
// lib/lakebase-errors.ts
export class DataApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message)
    this.name = 'DataApiError'
  }
  get isNotFound() { return this.status === 404 }
  get isConflict() { return this.status === 409 }
  get isUnauthorized() { return this.status === 401 }
  get isValidation() { return this.status === 422 }
}
```
