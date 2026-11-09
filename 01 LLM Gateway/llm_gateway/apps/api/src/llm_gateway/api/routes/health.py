from typing import Annotated

from fastapi import APIRouter, Depends

from llm_gateway.api.deps import get_runtime
from llm_gateway.core.runtime import GatewayRuntime

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(
    runtime: Annotated[GatewayRuntime, Depends(get_runtime)],
) -> dict[str, object]:
    database_ok = await runtime.database.ping()
    return {
        "status": "ready" if database_ok else "degraded",
        "database": "up" if database_ok else "down",
        "routes": len(runtime.config.routes),
    }
