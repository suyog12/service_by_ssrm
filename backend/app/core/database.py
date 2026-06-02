import asyncpg
from app.core.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None or _pool._closed:
        _pool = await asyncpg.create_pool(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            min_size=1,
            max_size=10,
            statement_cache_size=0,
        )
    return _pool


async def close_pool():
    global _pool
    if _pool is not None and not _pool._closed:
        await _pool.close()
    _pool = None


async def get_db():
    pool = await get_pool()
    async with pool.acquire() as connection:
        yield connection


async def get_tenant_db(schema_name: str):
    pool = await get_pool()
    async with pool.acquire() as connection:
        await connection.execute(
            f'SET search_path TO "{schema_name}", public'
        )
        yield connection