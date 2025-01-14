import asyncio
import datetime
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from models_library.app_diagnostics import AppStatusCheck
from servicelib.aiohttp import status

from ..._meta import API_VERSION, PROJECT_NAME
from ...core.health_checker import ApiServerHealthChecker, get_health_checker
from ...services_http.catalog import CatalogApi
from ...services_http.director_v2 import DirectorV2Api
from ...services_http.storage import StorageApi
from ...services_http.webserver import WebserverApi
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.services import get_api_client

router = APIRouter()


@router.get("/", include_in_schema=False, response_class=PlainTextResponse)
async def check_service_health(
    health_checker: Annotated[ApiServerHealthChecker, Depends(get_health_checker)]
):
    if not health_checker.healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="unhealthy"
        )

    return f"{__name__}@{datetime.datetime.now(tz=datetime.UTC).isoformat()}"


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
