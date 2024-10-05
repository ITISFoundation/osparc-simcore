from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, status
from models_library.projects_nodes_io import NodeID
from simcore_service_dynamic_scheduler.services.service_tracker._api import (
    get_all_tracked_services,
    remove_tracked_service,
)
from simcore_service_dynamic_scheduler.services.service_tracker._models import (
    TrackedServiceModel,
)

from ._dependencies import get_app

router = APIRouter()


@router.get("/services", response_model=dict[NodeID, TrackedServiceModel])
async def list_services(
    app: Annotated[FastAPI, Depends(get_app)]
) -> dict[NodeID, TrackedServiceModel]:
    return await get_all_tracked_services(app)


@router.delete(
    "/services/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_service(
    node_id: NodeID, app: Annotated[FastAPI, Depends(get_app)]
) -> None:
    await remove_tracked_service(app, node_id)
