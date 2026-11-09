from __future__ import annotations

import hashlib
import hmac

from llm_gateway.core.config import IdentityConfig
from llm_gateway.core.errors import AuthenticationError, RateLimitError
from llm_gateway.schemas.identity import IdentityContext
from llm_gateway.services.rate_limit import RateLimiter


class IdentityService:
    def __init__(self, config: IdentityConfig, limiter: RateLimiter) -> None:
        self._digests = [hashlib.sha256(key.encode()).digest() for key in config.api_keys]
        self._limiter = limiter

    async def identify(self, authorization: str | None) -> IdentityContext:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise AuthenticationError(
                "missing bearer API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raw_key = authorization[7:].strip()
        if not raw_key:
            raise AuthenticationError(
                "missing bearer API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        digest = hashlib.sha256(raw_key.encode()).digest()
        matched = any(hmac.compare_digest(digest, candidate) for candidate in self._digests)
        if not matched:
            raise AuthenticationError(
                "invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        key_id = digest.hex()[:12]
        identity = IdentityContext(subject=f"key_{key_id}", key_id=key_id)
        decision = await self._limiter.consume(key_id)
        if not decision.allowed:
            raise RateLimitError(
                "rate limit exceeded",
                headers={"Retry-After": str(decision.retry_after_seconds)},
                details={"retry_after_seconds": decision.retry_after_seconds},
            )
        return identity
