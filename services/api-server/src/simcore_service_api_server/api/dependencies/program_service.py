from typing import Annotated

from fastapi import Depends, FastAPI
from servicelib.fastapi.dependencies import get_app

from ..._service_programs import ProgramService
from ...services_rpc.catalog import CatalogService
from .catalog_service import get_catalog_service


async def get_program_service(
    app: Annotated[FastAPI, Depends(get_app)],
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> ProgramService:
    _program_service = ProgramService.get_from_app_state(app=app)
    _program_service._catalog_service = catalog_service
    return _program_service
