from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from models_library.api_schemas_directorv2.dynamic_services import (
    DynamicServiceGet,
)

from ...services import scheduler_interface
from ._dependencies import (
    get_app,
)

router = APIRouter()


@router.get("/ops/running-services")
async def running_services(
    app: Annotated[FastAPI, Depends(get_app)],
) -> list[DynamicServiceGet]:
    """returns all running dynamic services. Used by ops internall to determine
    when it is safe to shutdown the platform"""
    return await scheduler_interface.list_tracked_dynamic_services(
        app, user_id=None, project_id=None
    )
