from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import aiosqlite


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._connection: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self.path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA foreign_keys=ON")
        migration = Path(__file__).with_name("migrations") / "0001_initial.sql"
        await self._connection.executescript(migration.read_text(encoding="utf-8"))
        await self._connection.commit()

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("database is not connected")
        return self._connection

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        async with self._lock:
            cursor = await self.connection.execute(sql, params)
            await self.connection.commit()
            return cursor.lastrowid or 0

    async def fetchone(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        async with self._lock:
            cursor = await self.connection.execute(sql, params)
            row = await cursor.fetchone()
            return dict(row) if row is not None else None

    async def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        async with self._lock:
            cursor = await self.connection.execute(sql, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def ping(self) -> bool:
        try:
            result = await self.fetchone("SELECT 1 AS ok")
            return bool(result and result["ok"] == 1)
        except Exception:
            return False
