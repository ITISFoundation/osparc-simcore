from typing import Annotated

from fastapi import Depends, FastAPI
from servicelib.fastapi.dependencies import get_app
from simcore_service_api_server.services_rpc.catalog import CatalogService


async def get_catalog_service(
    app: Annotated[FastAPI, Depends(get_app)],
) -> CatalogService:
    catalog_service = CatalogService.get_from_app_state(app=app)
    assert isinstance(catalog_service, CatalogService)
    return catalog_service
