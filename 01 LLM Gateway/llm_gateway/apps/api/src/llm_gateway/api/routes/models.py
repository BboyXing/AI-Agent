from typing import Annotated

from fastapi import APIRouter, Depends

from llm_gateway.api.deps import IdentityDependency, get_model_router
from llm_gateway.gateway.router import ModelRouter
from llm_gateway.schemas.usage import ModelListResponse

router = APIRouter(tags=["models"])


@router.get("/api/v1/models", response_model=ModelListResponse)
async def list_models(
    identity: IdentityDependency,
    model_router: Annotated[ModelRouter, Depends(get_model_router)],
) -> ModelListResponse:
    del identity
    return model_router.model_list()
