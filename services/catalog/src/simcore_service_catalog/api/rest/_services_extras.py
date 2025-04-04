from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_directorv2.services import ServiceExtras
from models_library.services import ServiceKey, ServiceVersion

from .._dependencies.director import DirectorApi, get_director_api

router = APIRouter()


@router.get("/{service_key:path}/{service_version}/extras")
async def get_service_extras(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    director_client: Annotated[DirectorApi, Depends(get_director_api)],
) -> ServiceExtras:
    return await director_client.get_service_extras(service_key, service_version)
