from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_directorv2.services import ServiceExtras
from models_library.services import ServiceKey, ServiceVersion

from ...clients.director import DirectorClient
from ...service import services
from .._dependencies.director import get_director_client

router = APIRouter()


@router.get("/{service_key:path}/{service_version}/extras")
async def get_service_extras(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    director_client: Annotated[DirectorClient, Depends(get_director_client)],
) -> ServiceExtras:

    return await services.get_catalog_service_extras(
        director_client, service_key, service_version
    )
