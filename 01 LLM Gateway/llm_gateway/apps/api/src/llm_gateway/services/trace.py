from llm_gateway.services.usage import UsageService


class TraceService:
    """Small façade so routes and gateway code do not depend on persistence details."""

    def __init__(self, usage: UsageService) -> None:
        self._usage = usage

    async def event(self, request_id: str, event_type: str, **attributes: object) -> None:
        await self._usage.event(request_id, event_type, **attributes)
