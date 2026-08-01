import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, List, Optional, Tuple

import aiosqlite


class SQLiteConnectionPool:
    """Async SQLite connection pool with bounded size and idle reaping.

    Uses aiosqlite for fully asynchronous database access.
    Supports connection reuse, idle timeout reaping, and a bounded
    maximum number of concurrent connections.

    Usage::

        async with pool.acquire() as conn:
            cursor = await conn.execute(...)
            rows = await cursor.fetchall()
    """

    def __init__(self, db_path: str, max_connections: int = 10, idle_timeout: float = 300.0) -> None:
        """
        Args:
            db_path: Path to the SQLite database file.
            max_connections: Maximum number of connections the pool may hold.
            idle_timeout: Seconds after which an idle connection is eligible for reaping.
        """
        self._db_path = db_path
        self._max_connections = max_connections
        self._idle_timeout = idle_timeout

        # (connection, last_used_timestamp) for idle connections
        self._pool: List[Tuple[aiosqlite.Connection, float]] = []
        self._in_use = 0
        self._lock = asyncio.Lock()
        self._cond = asyncio.Condition(self._lock)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _create_connection(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self._db_path, timeout=15)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    async def _reap_idle_locked(self) -> None:
        """Remove and close connections that have been idle past the timeout."""
        now = time.monotonic()
        keep: List[Tuple[aiosqlite.Connection, float]] = []
        for conn, last_used in self._pool:
            if (now - last_used) > self._idle_timeout:
                try:
                    await conn.close()
                except Exception:
                    pass
            else:
                keep.append((conn, last_used))
        self._pool[:] = keep

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[aiosqlite.Connection]:
        """Acquire a connection from the pool (async context manager).

        Usage::

            async with pool.acquire() as conn:
                cursor = await conn.execute(...)
        """
        conn = await self._get()
        try:
            yield conn
        finally:
            await self._release(conn)

    async def _get(self) -> aiosqlite.Connection:
        async with self._lock:
            # Opportunistically reap idle connections before checking pool
            await self._reap_idle_locked()

            # 1. Return an idle connection if one exists
            if self._pool:
                conn, _ = self._pool.pop()
                self._in_use += 1
                return conn

            # 2. Create a new connection if under the limit
            if (len(self._pool) + self._in_use) < self._max_connections:
                self._in_use += 1
                return await self._create_connection()

            # 3. All connections are busy — wait until one is released
            while True:
                await self._cond.wait(timeout=30.0)
                # Recheck conditions after wake-up
                if self._pool:
                    conn, _ = self._pool.pop()
                    self._in_use += 1
                    return conn
                if (len(self._pool) + self._in_use) < self._max_connections:
                    self._in_use += 1
                    return await self._create_connection()

    async def _release(self, conn: aiosqlite.Connection) -> None:
        async with self._lock:
            self._pool.append((conn, time.monotonic()))
            self._in_use -= 1
            self._cond.notify()

    async def reap_idle(self) -> int:
        """Explicitly reap idle connections.

        Returns the number of connections that were closed.
        """
        async with self._lock:
            before = len(self._pool)
            await self._reap_idle_locked()
            return before - len(self._pool)

    async def close_all(self) -> None:
        """Close all **idle** connections.  Connections currently in use are
        **not** closed — they remain valid and will be returned to the pool
        (but should not be used after this call)."""
        async with self._lock:
            for conn, _ in self._pool:
                try:
                    await conn.close()
                except Exception:
                    pass
            self._pool.clear()

    # ------------------------------------------------------------------
    # Introspection methods (useful for diagnostics / testing)
    # ------------------------------------------------------------------

    async def total_connections(self) -> int:
        async with self._lock:
            return len(self._pool) + self._in_use

    async def idle_count(self) -> int:
        async with self._lock:
            return len(self._pool)

    async def in_use_count(self) -> int:
        async with self._lock:
            return self._in_use
