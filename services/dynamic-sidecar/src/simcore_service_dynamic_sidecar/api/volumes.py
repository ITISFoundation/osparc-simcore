from typing import Optional

from fastapi import APIRouter, Depends
from fastapi import Path as PathParam
from fastapi import status
from models_library.volumes import VolumeID
from pydantic import BaseModel

from ..modules.mounted_fs import MountedVolumes
from ..modules.volume_files import set_volume_state
from ._dependencies import get_mounted_volumes

router = APIRouter()


class PatchVolumeItem(BaseModel):
    requires_saving: bool
    was_saved: Optional[bool]


@router.patch(
    "/volumes/{id}",
    summary="Updates the state of the volume",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def patch_volume_state(
    item: PatchVolumeItem,
    volume_id: VolumeID = PathParam(..., alias="id"),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> None:
    await set_volume_state(
        mounted_volumes,
        volume_id,
        requires_saving=item.requires_saving,
        was_saved=item.was_saved,
    )
