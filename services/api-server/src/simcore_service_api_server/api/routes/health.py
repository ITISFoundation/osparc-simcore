import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from ...modules.catalog import CatalogApi
from ...modules.director_v2 import DirectorV2Api
from ..dependencies.services import get_api_client

router = APIRouter()


@router.get("/", include_in_schema=False, response_class=PlainTextResponse)
async def check_service_health():
    return f"{__name__}@{datetime.utcnow().isoformat()}"


@router.get("/state", include_in_schema=False)
async def get_service_state(
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    director2_api: DirectorV2Api = Depends(get_api_client(DirectorV2Api)),
):
    apis = (catalog_client, director2_api)
    heaths: List[bool] = await asyncio.gather(*[api.is_responsive() for api in apis])

    return {
        api.service_name: {"healthy": is_healty} for api, is_healty in zip(apis, heaths)
    }
