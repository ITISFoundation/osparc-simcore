from fastapi import APIRouter, Depends
from fastapi import Path as PathParam
from fastapi import status
from models_library.volumes import VolumeCategory
from pydantic import BaseModel
from servicelib.volumes_utils import VolumeStatus

from ..modules.mounted_fs import MountedVolumes
from ..modules.volume_files import set_volume_state
from ._dependencies import get_mounted_volumes

router = APIRouter()


class PutVolumeItem(BaseModel):
    status: VolumeStatus


@router.put(
    "/volumes/{id}",
    summary="Updates the state of the volume",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def patch_volume_state(
    item: PutVolumeItem,
    volume_category: VolumeCategory = PathParam(..., alias="id"),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> None:
    await set_volume_state(mounted_volumes, volume_category, status=item.status)
