import asyncpg
from app.core.config import settings


# Global connection pool
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            min_size=2,
            max_size=10,
        )
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def get_db():
    """
    Dependency — gives a connection from the pool.
    Use in endpoints: db: asyncpg.Connection = Depends(get_db)
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        yield connection


async def get_tenant_db(schema_name: str):
    """
    Returns a connection scoped to a tenant's private schema.
    Sets search_path so all queries hit that tenant's tables only.
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        await connection.execute(f'SET search_path TO "{schema_name}", public')
        yield connection