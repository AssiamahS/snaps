"""
snaps read API.

Three endpoints, one per table. Shared query shape so the handler is tiny:
    GET /doctors?state=NJ&city=Newark&last_name=Smith&limit=50

DB connection comes from env (PGHOST, PGUSER, PGPASSWORD, PGDATABASE). For
prod, drop this behind Cloudflare Workers or a reverse proxy; don't ship it
as the public origin.
"""
import os
from typing import Optional
from contextlib import asynccontextmanager

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Query

DSN = "postgresql://{u}:{p}@{h}:{port}/{db}".format(
    u=os.environ.get("PGUSER", "medchat_app"),
    p=os.environ.get("PGPASSWORD", ""),
    h=os.environ.get("PGHOST", "localhost"),
    port=os.environ.get("PGPORT", "5432"),
    db=os.environ.get("PGDATABASE", "medchat"),
)

TABLES = {
    "doctors":     "providers_doctors",
    "dentists":    "providers_dentists",
    "pharmacists": "providers_pharmacists",
}

pool: Optional[psycopg.AsyncConnection] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await psycopg.AsyncConnection.connect(DSN, row_factory=dict_row)
    try:
        yield
    finally:
        await pool.close()

app = FastAPI(title="snaps NPI API", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    async with pool.cursor() as cur:
        await cur.execute("SELECT 1 AS ok")
        row = await cur.fetchone()
    return {"status": "ok" if row and row["ok"] == 1 else "degraded"}


@app.get("/{kind}")
async def search(
    kind: str,
    state: Optional[str] = Query(None, min_length=2, max_length=2),
    city: Optional[str] = Query(None, max_length=100),
    last_name: Optional[str] = Query(None, max_length=100),
    taxonomy_prefix: Optional[str] = Query(None, min_length=2, max_length=10),
    limit: int = Query(50, ge=1, le=500),
):
    table = TABLES.get(kind)
    if not table:
        raise HTTPException(404, f"unknown kind '{kind}' — try {list(TABLES)}")

    where, params = [], []
    if state:
        where.append("state = %s"); params.append(state.upper())
    if city:
        where.append("city ILIKE %s"); params.append(city)
    if last_name:
        where.append("last_name ILIKE %s"); params.append(f"{last_name}%")
    if taxonomy_prefix:
        where.append("taxonomy_code LIKE %s"); params.append(f"{taxonomy_prefix}%")

    sql = f"""
        SELECT npi, first_name, last_name, middle_name, credential, taxonomy_code,
               addr_line1, addr_line2, city, state, zip, phone, enumeration_date
        FROM {table}
        {"WHERE " + " AND ".join(where) if where else ""}
        ORDER BY last_name, first_name
        LIMIT %s
    """
    params.append(limit)

    async with pool.cursor() as cur:
        await cur.execute(sql, params)
        rows = await cur.fetchall()
    return {"count": len(rows), "results": rows}


@app.get("/{kind}/{npi}")
async def get_one(kind: str, npi: int):
    table = TABLES.get(kind)
    if not table:
        raise HTTPException(404, f"unknown kind '{kind}'")
    async with pool.cursor() as cur:
        await cur.execute(f"SELECT * FROM {table} WHERE npi = %s", (npi,))
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, f"NPI {npi} not found in {kind}")
    return row
