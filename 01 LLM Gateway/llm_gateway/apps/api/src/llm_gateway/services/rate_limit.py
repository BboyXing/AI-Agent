from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True, frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


class RateLimiter(Protocol):
    async def consume(self, key: str) -> RateLimitDecision: ...


class MemoryFixedWindowLimiter:
    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._windows: dict[str, tuple[int, int]] = {}
        self._lock = asyncio.Lock()

    async def consume(self, key: str) -> RateLimitDecision:
        now = self.clock()
        bucket = int(now // self.window_seconds)
        async with self._lock:
            stored_bucket, count = self._windows.get(key, (bucket, 0))
            if stored_bucket != bucket:
                stored_bucket, count = bucket, 0
            if count >= self.limit:
                elapsed = now - (bucket * self.window_seconds)
                retry_after = max(1, math.ceil(self.window_seconds - elapsed))
                self._windows[key] = (stored_bucket, count)
                return RateLimitDecision(False, retry_after)
            self._windows[key] = (stored_bucket, count + 1)
            return RateLimitDecision(True)
