from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from llm_gateway.api.deps import IdentityDependency, get_usage_repository
from llm_gateway.persistence.repository import UsageRepository
from llm_gateway.schemas.usage import CallDetail, CallPage, UsageSummary

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])


@router.get("/summary", response_model=UsageSummary)
async def usage_summary(
    identity: IdentityDependency,
    repository: Annotated[UsageRepository, Depends(get_usage_repository)],
    from_at: Annotated[datetime | None, Query(alias="from")] = None,
    to_at: Annotated[datetime | None, Query(alias="to")] = None,
    route: str | None = None,
    status: str | None = None,
) -> UsageSummary:
    del identity
    start, end = _range(from_at, to_at)
    return await repository.summary(
        from_time=start.isoformat(),
        to_time=end.isoformat(),
        route=route,
        status=status,
    )


@router.get("/calls", response_model=CallPage)
async def list_calls(
    identity: IdentityDependency,
    repository: Annotated[UsageRepository, Depends(get_usage_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    from_at: Annotated[datetime | None, Query(alias="from")] = None,
    to_at: Annotated[datetime | None, Query(alias="to")] = None,
    route: str | None = None,
    status: str | None = None,
) -> CallPage:
    del identity
    start, end = _range(from_at, to_at)
    return await repository.list_calls(
        limit=limit,
        offset=offset,
        route=route,
        status=status,
        from_time=start.isoformat(),
        to_time=end.isoformat(),
    )


@router.get("/calls/{request_id}", response_model=CallDetail)
async def call_detail(
    request_id: str,
    identity: IdentityDependency,
    repository: Annotated[UsageRepository, Depends(get_usage_repository)],
) -> CallDetail | JSONResponse:
    del identity
    detail = await repository.call_detail(request_id)
    if detail is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "message": f"request {request_id!r} was not found",
                    "type": "not_found",
                    "code": "request_not_found",
                }
            },
        )
    return detail


def _range(
    from_at: datetime | None,
    to_at: datetime | None,
) -> tuple[datetime, datetime]:
    end = to_at or datetime.now(UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    start = from_at or (end - timedelta(days=30))
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    return start, end
