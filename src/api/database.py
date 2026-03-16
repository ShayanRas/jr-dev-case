"""Database connection and query functions.

Uses asyncpg for async PostgreSQL access. The connection pool is created
at app startup and closed at shutdown via FastAPI's lifespan.
"""

import os
from typing import Any, Optional

import asyncpg

# Module-level pool reference, initialized by init_pool()
_pool: Optional[asyncpg.Pool] = None


async def init_pool() -> asyncpg.Pool:
    """Create the connection pool. Called once at app startup."""
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres@postgres:5432/case_db",
        ),
        min_size=2,
        max_size=10,
    )
    return _pool


async def close_pool() -> None:
    """Close the connection pool. Called at app shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """Get the current connection pool. Raises if not initialized."""
    if _pool is None:
        raise RuntimeError(
            "Database pool not initialized. Call init_pool() first."
        )
    return _pool


# --- Query functions ---


async def store_search_result(
    user_id: str, org_id: str, query: str, results: list[dict[str, Any]]
) -> int:
    """Store a search result in the database. Returns the new row ID."""
    import json

    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO search_history (user_id, org_id, query, results)
        VALUES ($1, $2, $3, $4::jsonb)
        RETURNING id
        """,
        user_id,
        org_id,
        query,
        json.dumps(results),
    )
    return row["id"]


async def fetch_search_results(
    user_id: str, org_id: Optional[str] = None, limit: int = 50
) -> list[dict[str, Any]]:
    """Fetch search results for a user, optionally filtered by org."""
    pool = get_pool()
    if org_id:
        rows = await pool.fetch(
            """
            SELECT id, user_id, org_id, query, results, created_at
            FROM search_history
            WHERE user_id = $1 AND org_id = $2
            ORDER BY created_at DESC
            LIMIT $3
            """,
            user_id,
            org_id,
            limit,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT id, user_id, org_id, query, results, created_at
            FROM search_history
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
    return [dict(r) for r in rows]
