from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi import Path as PathParam
from fastapi import status
from models_library.sidecar_volumes import VolumeCategory, VolumeState, VolumeStatus
from pydantic import BaseModel

from ...models.shared_store import SharedStore
from ._dependencies import get_shared_store

router = APIRouter()


class PutVolumeItem(BaseModel):
    status: VolumeStatus


@router.put(
    "/volumes/{id}",
    summary="Updates the state of the volume",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def put_volume_state(
    item: PutVolumeItem,
    volume_category: Annotated[VolumeCategory, PathParam(..., alias="id")],
    shared_store: Annotated[SharedStore, Depends(get_shared_store)],
) -> None:
    async with shared_store:
        shared_store.volume_states[volume_category] = VolumeState(status=item.status)
