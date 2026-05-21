# Python Backend Connection Templates (PG Wire)

All Python backends connect via PostgreSQL wire protocol with OAuth token rotation.
The `get_lakebase_token()` function comes from `references/security-backend.md`.

---

## psycopg3 (recommended)

> Install: `pip install "psycopg[binary]"`

**Sync:**
```python
# db/connection.py
import os
import time
import psycopg
from auth.token_rotator import get_lakebase_token

_CONNECT_PARAMS = lambda: dict(
    host=os.environ["LAKEBASE_HOST"],
    port=int(os.environ.get("LAKEBASE_PORT", "5432")),
    dbname=os.environ["LAKEBASE_DB"],
    user=os.environ["LAKEBASE_USER"],
    password=get_lakebase_token(),
    sslmode="require",
)

def get_conn() -> psycopg.Connection:
    for attempt in range(3):
        try:
            return psycopg.connect(**_CONNECT_PARAMS())
        except psycopg.OperationalError:
            if attempt == 2:
                raise
            time.sleep(0.2 * (attempt + 1))
```

**Async (FastAPI):**
```python
# db/async_connection.py
import os
import asyncio
import psycopg
from auth.token_rotator import get_lakebase_token

async def get_async_conn() -> psycopg.AsyncConnection:
    for attempt in range(3):
        try:
            return await psycopg.AsyncConnection.connect(
                host=os.environ["LAKEBASE_HOST"],
                port=int(os.environ.get("LAKEBASE_PORT", "5432")),
                dbname=os.environ["LAKEBASE_DB"],
                user=os.environ["LAKEBASE_USER"],
                password=get_lakebase_token(),
                sslmode="require",
            )
        except psycopg.OperationalError:
            if attempt == 2:
                raise
            await asyncio.sleep(0.2 * (attempt + 1))

async def get_db():
    conn = await get_async_conn()
    try:
        yield conn
    finally:
        await conn.close()
```

---

## psycopg2 (legacy)

```python
# db/connection.py
import os
import time
import psycopg2
from auth.token_rotator import get_lakebase_token

def get_conn() -> psycopg2.extensions.connection:
    for attempt in range(3):
        try:
            return psycopg2.connect(
                host=os.environ["LAKEBASE_HOST"],
                port=int(os.environ.get("LAKEBASE_PORT", "5432")),
                dbname=os.environ["LAKEBASE_DB"],
                user=os.environ["LAKEBASE_USER"],
                password=get_lakebase_token(),
                sslmode="require",
            )
        except psycopg2.OperationalError:
            if attempt == 2:
                raise
            time.sleep(0.2 * (attempt + 1))
```

---

## asyncpg (high-throughput)

```python
# db/async_connection.py
import os
import asyncio
import asyncpg
from auth.token_rotator import get_lakebase_token

async def get_async_conn() -> asyncpg.Connection:
    for attempt in range(3):
        try:
            return await asyncpg.connect(
                host=os.environ["LAKEBASE_HOST"],
                port=int(os.environ.get("LAKEBASE_PORT", "5432")),
                database=os.environ["LAKEBASE_DB"],
                user=os.environ["LAKEBASE_USER"],
                password=get_lakebase_token(),
                ssl="require",
            )
        except (asyncpg.TooManyConnectionsError, OSError):
            if attempt == 2:
                raise
            await asyncio.sleep(0.2 * (attempt + 1))

async def get_db():
    conn = await get_async_conn()
    try:
        yield conn
    finally:
        await conn.close()
```

---

## SQLAlchemy

```python
# db/engine.py
import os
import time
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from auth.token_rotator import get_lakebase_token

def get_engine():
    engine = create_engine(
        os.environ["DATABASE_URL"],
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"},
    )

    @event.listens_for(engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams):
        cparams["password"] = get_lakebase_token()
        for attempt in range(3):
            try:
                return dialect.dbapi.connect(*cargs, **cparams)
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(0.2 * (attempt + 1))
        return None

    return engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## Django ORM

```python
# myapp/lakebase_backend.py
from django.db.backends.postgresql import base
from auth.token_rotator import get_lakebase_token

class DatabaseWrapper(base.DatabaseWrapper):
    def get_new_connection(self, conn_params):
        return super().get_new_connection({**conn_params, "password": get_lakebase_token()})
```

```python
# settings.py
import os

DATABASES = {
    "default": {
        "ENGINE": "myapp.lakebase_backend",
        "HOST": os.environ["LAKEBASE_HOST"],
        "PORT": os.environ.get("LAKEBASE_PORT", "5432"),
        "NAME": os.environ["LAKEBASE_DB"],
        "USER": os.environ["LAKEBASE_USER"],
        "PASSWORD": "",
        "OPTIONS": {"sslmode": "require"},
        "CONN_MAX_AGE": 0,
    }
}
```
