from __future__ import annotations

from typing import Any


class GatewayError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.details = details or {}
        self.headers = headers or {}


class AuthenticationError(GatewayError):
    status_code = 401
    code = "invalid_api_key"


class RateLimitError(GatewayError):
    status_code = 429
    code = "rate_limit_exceeded"


class RouteNotFoundError(GatewayError):
    status_code = 404
    code = "route_not_found"


class RequestRejectedError(GatewayError):
    status_code = 400
    code = "invalid_request"


class ProviderUnavailableError(GatewayError):
    status_code = 502
    code = "all_candidates_failed"


class UpstreamError(GatewayError):
    status_code = 502
    code = "upstream_error"

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        retryable: bool,
        status_code: int | None = None,
        code: str = "upstream_error",
    ) -> None:
        super().__init__(
            message,
            status_code=status_code,
            code=code,
            details={"provider": provider},
        )
        self.provider = provider
        self.retryable = retryable


class StructuredOutputError(UpstreamError):
    code = "response_validation_failed"

    def __init__(self, provider: str, errors: str) -> None:
        super().__init__(
            "model response did not match the requested JSON schema",
            provider=provider,
            retryable=True,
            status_code=502,
            code="response_validation_failed",
        )
        self.validation_errors = errors
