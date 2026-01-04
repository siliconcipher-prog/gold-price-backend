from fastapi import FastAPI, Query, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List
import os
import uuid

from psycopg_pool import ConnectionPool
from psycopg import DatabaseError as PsycopgError

from logging_config import logger
from exceptions import DatabaseError
from cache import get_cache, set_cache
from rate_limiter import is_rate_limited
from rate_limiter import get_client_ip

ENV = os.getenv("ENV", "dev")

# =========================
# APP SETUP
# =========================

app = FastAPI(
    title="Gold Price API",
    version="1.0.0",
    docs_url=None if ENV == "prod" else "/docs",
    redoc_url=None if ENV == "prod" else "/redoc"
)

# =========================
# CORS
# =========================



ALLOWED_ORIGINS = (
    ["https://goldpricetoday.in", "https://www.goldpricetoday.in"]
    if ENV == "prod"
    else [
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "https://gold-price-frontend.netlify.app",
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# =========================
# DB
# =========================

PG_DSN = os.getenv(
    "PG_DSN",
    "host=localhost port=5432 user=postgres password=1234 dbname=gold_tracker"
)

db_pool = ConnectionPool(PG_DSN, min_size=2, max_size=10)

# =========================
# MIDDLEWARES
# =========================

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.headers.get(
        "X-Request-ID", str(uuid.uuid4())
    )
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)

    if request.url.path not in {"/health", "/metrics", "/version"}:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        if ENV == "prod":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    ip = get_client_ip(request) 

    if path.startswith("/api/v1/gold/full"):
        if is_rate_limited(f"gold:{ip}", 60, 60):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": "60"}
            )

    if path.startswith("/api/v1/cities"):
        if is_rate_limited(f"cities:{ip}", 120, 60):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": "60"}
            )

    return await call_next(request)

# =========================
# API
# =========================

@app.get("/api/v1/gold/full")
def gold_full(city: str = Query(..., min_length=2)):
    city_key = city.lower().strip()
    cache_key = f"gold:{city_key}"

    cached = get_cache(cache_key)
    if cached:
        return cached

    sql = """
   WITH latest AS (
    SELECT
        price_24k,
        price_22k,
        price_18k,
        recorded_on,
        recorded_at,
        source
    FROM city_slab_map c
    JOIN gold_price_slabs s USING (slab_name)
    WHERE LOWER(c.city_name) = LOWER(%s)
    ORDER BY recorded_on DESC
    LIMIT 1
),
history AS (
    SELECT
        recorded_on,
        price_24k,
        price_22k,
        price_18k
    FROM city_slab_map c
    JOIN gold_price_slabs s USING (slab_name)
    WHERE LOWER(c.city_name) = LOWER(%s)
    ORDER BY recorded_on DESC
    LIMIT 7
)
SELECT
    latest.price_24k,
    latest.price_22k,
    latest.price_18k,
    latest.recorded_on,
    latest.recorded_at,
    latest.source,
    json_agg(
        json_build_object(
            'date', history.recorded_on,
            '24K', history.price_24k,
            '22K', history.price_22k,
            '18K', history.price_18k
        )
        ORDER BY history.recorded_on
    ) AS history
FROM latest
JOIN history ON true
GROUP BY
    latest.price_24k,
    latest.price_22k,
    latest.price_18k,
    latest.recorded_on,
    latest.recorded_at,
    latest.source;

    """

    try:
        with db_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (city_key, city_key))
                row = cur.fetchone()
    except PsycopgError:
        raise DatabaseError()

    if not row:
        raise HTTPException(404, "City not supported")

    response = {
        "city": city.title(),
        "prices": {
            "24K": float(row[0]),
            "22K": float(row[1]),
            "18K": float(row[2]),
        },
        "date": row[3],
        "last_updated": row[4],
        "history": row[6],
    }

    set_cache(cache_key, response, 300)
    return response


@app.get("/api/v1/cities", response_model=List[str])
def cities(q: str = Query(..., min_length=2)):
    key = f"cities:{q.lower()}"
    cached = get_cache(key)
    if cached:
        return cached

    sql = """
    SELECT city_name
    FROM city_slab_map
    WHERE city_name ILIKE %s
    ORDER BY city_name
    LIMIT 10;
    """

    with db_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (f"{q}%",))
            rows = cur.fetchall()

    result = [r[0] for r in rows]
    set_cache(key, result, 3600)
    return result

# =========================
# HEALTH
# =========================

@app.get("/health")
def health():
    return {"status": "ok"}
