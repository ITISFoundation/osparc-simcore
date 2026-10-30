from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from models_library.api_schemas_directorv2.dynamic_services import (
    DynamicServiceGet,
)

from ...services import common_interface
from ...services.t_scheduler import RunningWorkflowInfo, get_workflow_engine
from ._dependencies import get_app

router = APIRouter()


@router.get("/ops/running-services")
async def running_services(
    app: Annotated[FastAPI, Depends(get_app)],
) -> list[DynamicServiceGet]:
    """returns all running dynamic services. Used by ops internally to determine
    when it is safe to shutdown the platform"""
    return await common_interface.list_tracked_dynamic_services(app, user_id=None, project_id=None)


@router.get("/ops/temporalio-workflows")
async def list_workflows(
    app: Annotated[FastAPI, Depends(get_app)],
) -> list[RunningWorkflowInfo]:
    """List all running Temporalio workflows on the scheduler task queue."""
    engine = get_workflow_engine(app)
    return await engine.list_running_workflows()


@router.post("/ops/temporalio-workflows:shutdown")
async def shutdown_workflows(
    app: Annotated[FastAPI, Depends(get_app)],
) -> dict[str, int]:
    """Cancel all running Temporalio workflows, triggering saga compensation."""
    engine = get_workflow_engine(app)
    cancelled = await engine.cancel_all_workflows()
    return {"cancelled": cancelled}
