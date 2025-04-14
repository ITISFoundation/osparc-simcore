from typing import Annotated, Any

from fastapi import APIRouter, Depends
from models_library.services import ServiceKey, ServiceVersion

from ...clients.director import DirectorClient
from .._dependencies.director import get_director_client

router = APIRouter()


@router.get("/{service_key:path}/{service_version}/labels")
async def get_service_labels(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    director_client: Annotated[DirectorClient, Depends(get_director_client)],
) -> dict[str, Any]:
    return await director_client.get_service_labels(service_key, service_version)
