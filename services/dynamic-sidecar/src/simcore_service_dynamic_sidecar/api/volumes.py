from typing import Literal

from fastapi import APIRouter, Depends, status

from ..modules.mounted_fs import MountedVolumes
from ..modules.volume_files import (
    set_volume_state_in_agent_file_outputs_saved,
    set_volume_state_in_agent_file_states_saved,
)
from ._dependencies import get_mounted_volumes

router = APIRouter()


@router.post(
    "/volumes/{volume_id}/state:saved",
    summary="Marks the volume's content as saved to S3",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def set_volume_state_as_saved(
    volume_id: Literal["states", "outputs"],
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> None:
    if volume_id == "states":
        await set_volume_state_in_agent_file_states_saved(mounted_volumes)
    elif volume_id == "outputs":
        await set_volume_state_in_agent_file_outputs_saved(mounted_volumes)
