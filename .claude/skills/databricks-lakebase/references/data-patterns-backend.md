# Backend Data Patterns — Python Query Modules (PG Wire)

For each entity, generate `db/queries/[entity].py`.

---

## CRUD Template

```python
# db/queries/[entity].py
from db.connection import get_conn


def get_all_[entities](*, after_id: int = 0, limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, [columns] FROM [entity] WHERE id > %s ORDER BY id LIMIT %s",
                (after_id, limit),
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_[entity]_by_id([entity]_id: int) -> dict | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, [columns] FROM [entity] WHERE id = %s",
                ([entity]_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            cols = [d.name for d in cur.description]
            return dict(zip(cols, row))


def create_[entity](data: dict) -> int:
    from psycopg import sql
    cols = list(data.keys())
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
        sql.Identifier("[entity]"),
        sql.SQL(", ").join(sql.Identifier(c) for c in cols),
        sql.SQL(", ").join(sql.Placeholder() for _ in cols),
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(data[c] for c in cols))
            new_id: int = cur.fetchone()[0]
    return new_id


def update_[entity]([entity]_id: int, data: dict) -> None:
    if not data:
        return
    from psycopg import sql
    cols = list(data.keys())
    query = sql.SQL("UPDATE {} SET {} WHERE id = %s").format(
        sql.Identifier("[entity]"),
        sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(c)) for c in cols),
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (*[data[c] for c in cols], [entity]_id))


def delete_[entity]([entity]_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM [entity] WHERE id = %s", ([entity]_id,))
```

---

## Bulk Insert

```python
def bulk_create_[entities](items: list[dict]) -> None:
    if not items:
        return
    from psycopg import sql
    cols = list(items[0].keys())
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier("[entity]"),
        sql.SQL(", ").join(sql.Identifier(c) for c in cols),
        sql.SQL(", ").join(sql.Placeholder() for _ in cols),
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(query, [tuple(item[c] for c in cols) for item in items])
```

---

## Multi-table Transactions

```python
def create_[parent]_with_[children](
    parent_data: dict,
    children: list[dict],
) -> int:
    from psycopg import sql
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO [parent] ([cols]) VALUES ([placeholders]) RETURNING id",
                tuple(parent_data.values()),
            )
            parent_id: int = cur.fetchone()[0]
            if children:
                child_cols = list(children[0].keys())
                child_query = sql.SQL(
                    "INSERT INTO {} ({}, {}) VALUES ({}, {})"
                ).format(
                    sql.Identifier("[child]"),
                    sql.Identifier("[parent]_id"),
                    sql.SQL(", ").join(sql.Identifier(c) for c in child_cols),
                    sql.Placeholder(),
                    sql.SQL(", ").join(sql.Placeholder() for _ in child_cols),
                )
                cur.executemany(
                    child_query,
                    [(parent_id, *tuple(c.values())) for c in children],
                )
    return parent_id
```
