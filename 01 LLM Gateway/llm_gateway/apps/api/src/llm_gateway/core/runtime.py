from __future__ import annotations

from dataclasses import dataclass

import httpx

from llm_gateway.core.config import GatewayConfig, load_gateway_config
from llm_gateway.core.logging import configure_logging
from llm_gateway.gateway.adapters.anthropic import AnthropicAdapter
from llm_gateway.gateway.adapters.base import ProviderAdapter
from llm_gateway.gateway.adapters.openai import OpenAICompatibleAdapter
from llm_gateway.gateway.router import ModelRouter
from llm_gateway.gateway.service import GatewayService
from llm_gateway.persistence.db import Database
from llm_gateway.persistence.repository import UsageRepository
from llm_gateway.services.identity import IdentityService
from llm_gateway.services.prompts import PromptRegistry
from llm_gateway.services.rate_limit import MemoryFixedWindowLimiter
from llm_gateway.services.trace import TraceService
from llm_gateway.services.usage import UsageService


@dataclass(slots=True)
class GatewayRuntime:
    config: GatewayConfig
    prompts: PromptRegistry
    database: Database
    usage_repository: UsageRepository
    usage: UsageService
    trace: TraceService
    http: httpx.AsyncClient
    model_router: ModelRouter
    adapters: dict[str, ProviderAdapter]
    gateway: GatewayService
    identity: IdentityService
    _owns_http: bool = True

    async def close(self) -> None:
        await self.database.close()
        if self._owns_http:
            await self.http.aclose()


async def build_runtime(
    config: GatewayConfig | None = None,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> GatewayRuntime:
    configure_logging()
    config = config or load_gateway_config()
    prompt_names = {route.prompt for route in config.routes.values()}
    prompts = PromptRegistry(config.prompts_dir, prompt_names)
    database = Database(config.database_file)
    await database.connect()
    repository = UsageRepository(database)
    usage = UsageService(repository)
    trace = TraceService(usage)
    http = http_client or httpx.AsyncClient(follow_redirects=False)
    adapters: dict[str, ProviderAdapter] = {
        "openai": OpenAICompatibleAdapter(http),
        "anthropic": AnthropicAdapter(http),
    }
    model_router = ModelRouter(config)
    gateway = GatewayService(
        router=model_router,
        prompts=prompts,
        usage=usage,
        adapters=adapters,
    )
    limiter = MemoryFixedWindowLimiter(
        limit=config.identity.rate_limit.requests,
        window_seconds=config.identity.rate_limit.window_seconds,
    )
    identity = IdentityService(config.identity, limiter)
    return GatewayRuntime(
        config=config,
        prompts=prompts,
        database=database,
        usage_repository=repository,
        usage=usage,
        trace=trace,
        http=http,
        model_router=model_router,
        adapters=adapters,
        gateway=gateway,
        identity=identity,
        _owns_http=http_client is None,
    )


def mount_runtime(app: object, runtime: GatewayRuntime) -> None:
    app.state.runtime = runtime
    app.state.config = runtime.config
    app.state.prompts = runtime.prompts
    app.state.usage = runtime.usage
    app.state.usage_repository = runtime.usage_repository
    app.state.http = runtime.http
    app.state.model_router = runtime.model_router
    app.state.identity = runtime.identity
    app.state.gateway = runtime.gateway


def unmount_runtime(app: object) -> None:
    for name in (
        "runtime",
        "config",
        "prompts",
        "usage",
        "usage_repository",
        "http",
        "model_router",
        "identity",
        "gateway",
    ):
        if hasattr(app.state, name):
            delattr(app.state, name)
