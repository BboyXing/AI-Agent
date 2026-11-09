from __future__ import annotations

import pytest

from llm_gateway.core.config import IdentityConfig
from llm_gateway.core.errors import AuthenticationError, RateLimitError
from llm_gateway.services.identity import IdentityService
from llm_gateway.services.rate_limit import MemoryFixedWindowLimiter


@pytest.mark.asyncio
async def test_identity_authenticates_and_limits_by_key() -> None:
    now = 0.0
    limiter = MemoryFixedWindowLimiter(limit=2, window_seconds=10, clock=lambda: now)
    service = IdentityService(
        IdentityConfig(
            api_keys=["test-key"],
            rate_limit={"requests": 2, "window_seconds": 10},
        ),
        limiter,
    )

    first = await service.identify("Bearer test-key")
    second = await service.identify("Bearer test-key")
    assert first.key_id == second.key_id

    with pytest.raises(RateLimitError) as raised:
        await service.identify("Bearer test-key")
    assert raised.value.headers["Retry-After"] == "10"

    now = 10.0
    await service.identify("Bearer test-key")


@pytest.mark.asyncio
async def test_identity_rejects_missing_and_invalid_keys() -> None:
    service = IdentityService(
        IdentityConfig(api_keys=["test-key"], rate_limit={"requests": 5, "window_seconds": 60}),
        MemoryFixedWindowLimiter(limit=5, window_seconds=60),
    )

    with pytest.raises(AuthenticationError):
        await service.identify(None)
    with pytest.raises(AuthenticationError):
        await service.identify("Bearer wrong")
