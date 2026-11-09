from __future__ import annotations

from dataclasses import dataclass

from llm_gateway.core.config import GatewayConfig, ModelConfig, ProviderConfig, RouteConfig
from llm_gateway.core.errors import RouteNotFoundError
from llm_gateway.schemas.usage import (
    ModelCandidateInfo,
    ModelListResponse,
    ModelRouteInfo,
)


@dataclass(slots=True, frozen=True)
class Candidate:
    name: str
    model: ModelConfig
    provider_name: str
    provider: ProviderConfig


@dataclass(slots=True, frozen=True)
class ResolvedRoute:
    name: str
    prompt: str
    candidates: tuple[Candidate, ...]


class ModelRouter:
    def __init__(self, config: GatewayConfig) -> None:
        self._config = config

    def resolve(self, route_name: str) -> ResolvedRoute:
        try:
            route = self._config.routes[route_name]
        except KeyError as exc:
            raise RouteNotFoundError(f"unknown model route: {route_name}") from exc
        return ResolvedRoute(
            name=route_name,
            prompt=route.prompt,
            candidates=tuple(self._candidate(name) for name in route.candidates),
        )

    def _candidate(self, name: str) -> Candidate:
        model = self._config.models[name]
        provider = self._config.providers[model.provider]
        return Candidate(
            name=name,
            model=model,
            provider_name=model.provider,
            provider=provider,
        )

    def model_list(self) -> ModelListResponse:
        routes: list[ModelRouteInfo] = []
        for route_name, route in self._config.routes.items():
            routes.append(self._route_info(route_name, route))
        return ModelListResponse(data=routes)

    def _route_info(self, route_name: str, route: RouteConfig) -> ModelRouteInfo:
        candidates: list[ModelCandidateInfo] = []
        for candidate_name in route.candidates:
            candidate = self._candidate(candidate_name)
            candidates.append(
                ModelCandidateInfo(
                    id=candidate.name,
                    provider=candidate.provider_name,
                    model=candidate.model.model,
                    available=candidate.provider.available,
                )
            )
        return ModelRouteInfo(
            id=route_name,
            prompt=route.prompt,
            candidates=candidates,
        )
