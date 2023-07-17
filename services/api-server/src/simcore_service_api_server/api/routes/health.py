import asyncio
import datetime
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from models_library.app_diagnostics import AppStatusCheck

from ..._meta import API_VERSION, PROJECT_NAME
from ...services.catalog import CatalogApi
from ...services.director_v2 import DirectorV2Api
from ...services.storage import StorageApi
from ...services.webserver import WebserverApi
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.services import get_api_client

router = APIRouter()


@router.get("/", include_in_schema=False, response_class=PlainTextResponse)
async def check_service_health():
    return f"{__name__}@{datetime.datetime.now(tz=datetime.timezone.utc).isoformat()}"


@router.get(
    "/state",
    include_in_schema=False,
    response_model=AppStatusCheck,
    response_model_exclude_unset=True,
)
async def get_service_state(
    catalog_client: Annotated[CatalogApi, Depends(get_api_client(CatalogApi))],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    storage_client: Annotated[StorageApi, Depends(get_api_client(StorageApi))],
    webserver_client: Annotated[WebserverApi, Depends(get_api_client(WebserverApi))],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    apis = (
        catalog_client,
        director2_api,
        storage_client,
        webserver_client,
    )
    healths = await asyncio.gather(
        *[api.is_responsive() for api in apis],
        return_exceptions=False,
    )

    return AppStatusCheck(
        app_name=PROJECT_NAME,
        version=API_VERSION,
        services={
            api.service_name: {
                "healthy": bool(is_healty),
            }
            for api, is_healty in zip(apis, healths, strict=True)
        },
        url=url_for("get_service_state"),
    )
