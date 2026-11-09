from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from llm_gateway.gateway.router import Candidate
from llm_gateway.schemas.gateway import GatewayRequest, GatewayResult, UsageCounts


@dataclass(slots=True, frozen=True)
class AdapterStreamEvent:
    kind: Literal["delta", "usage", "finish"]
    text: str = ""
    usage: UsageCounts | None = None
    finish_reason: str = "stop"


class ProviderAdapter(ABC):
    @abstractmethod
    async def complete(self, candidate: Candidate, request: GatewayRequest) -> GatewayResult:
        raise NotImplementedError

    @abstractmethod
    def stream(
        self,
        candidate: Candidate,
        request: GatewayRequest,
    ) -> AsyncIterator[AdapterStreamEvent]:
        raise NotImplementedError
