from typing import Annotated, Any

from fastapi import APIRouter, Depends
from models_library.services import ServiceKey, ServiceVersion

from ...services.director import DirectorApi
from .._dependencies.director import get_director_api

router = APIRouter()


@router.get("/{service_key:path}/{service_version}/labels")
async def get_service_labels(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    director_client: Annotated[DirectorApi, Depends(get_director_api)],
) -> dict[str, Any]:
    return await director_client.get_service_labels(service_key, service_version)
