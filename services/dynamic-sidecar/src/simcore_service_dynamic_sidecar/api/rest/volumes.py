from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, status
from fastapi import Path as PathParam
from models_library.sidecar_volumes import VolumeCategory, VolumeStatus
from pydantic import BaseModel

from ...services import volumes
from ._dependencies import get_application

router = APIRouter()


class PutVolumeItem(BaseModel):
    status: VolumeStatus


@router.put("/volumes/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def put_volume_state(
    item: PutVolumeItem,
    app: Annotated[FastAPI, Depends(get_application)],
    volume_category: Annotated[VolumeCategory, PathParam(..., alias="id")],
) -> None:
    """Updates the state of the volume"""
    await volumes.update_volume_status(
        app, status=item.status, category=volume_category
    )
