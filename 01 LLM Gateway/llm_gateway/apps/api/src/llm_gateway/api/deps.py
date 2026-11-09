from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request

from llm_gateway.schemas.identity import IdentityContext

if TYPE_CHECKING:
    from llm_gateway.core.runtime import GatewayRuntime
    from llm_gateway.gateway.router import ModelRouter
    from llm_gateway.gateway.service import GatewayService
    from llm_gateway.persistence.repository import UsageRepository


def get_runtime(request: Request) -> GatewayRuntime:
    return request.app.state.runtime


def get_gateway(request: Request) -> GatewayService:
    return request.app.state.gateway


def get_model_router(request: Request) -> ModelRouter:
    return request.app.state.model_router


def get_usage_repository(request: Request) -> UsageRepository:
    return request.app.state.usage_repository


async def get_identity(request: Request) -> IdentityContext:
    return await request.app.state.identity.identify(request.headers.get("authorization"))


IdentityDependency = Annotated[IdentityContext, Depends(get_identity)]
