import asyncio
from datetime import datetime
from typing import Callable, Tuple

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from models_library.app_diagnostics import AppStatusCheck

from ..._meta import api_version, project_name
from ...modules.catalog import CatalogApi
from ...modules.director_v2 import DirectorV2Api
from ...modules.storage import StorageApi
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.services import get_api_client

router = APIRouter()


@router.get("/", include_in_schema=False, response_class=PlainTextResponse)
async def check_service_health():
    return f"{__name__}@{datetime.utcnow().isoformat()}"


@router.get("/state", include_in_schema=False)
async def get_service_state(
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    director2_api: DirectorV2Api = Depends(get_api_client(DirectorV2Api)),
    storage_client: StorageApi = Depends(get_api_client(StorageApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    apis = (catalog_client, director2_api, storage_client)
    heaths: Tuple[bool] = await asyncio.gather(*[api.is_responsive() for api in apis])

    current_status = AppStatusCheck(
        app_name=project_name,
        version=api_version,
        services={
            api.service_name: {"healthy": is_healty}
            for api, is_healty in zip(apis, heaths)
        },
        url=url_for("get_service_state"),
    )
    resp = current_status.dict(exclude_unset=True)
    resp.update(docs_dev_url=url_for("swagger_ui_html"))
    return resp
