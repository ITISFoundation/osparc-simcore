import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Union

import aiofiles
from aiofiles import os as aiofiles_os
from servicelib.volumes_utils import (
    AGENT_FILE_NAME,
    HIDDEN_FILE_NAME,
    VolumeState,
    save_volume_state,
)

from .mounted_fs import MountedVolumes

chmod = aiofiles_os.wrap(os.chmod)  # type: ignore


class VolumeID(str, Enum):
    OUTPUTS = "outputs"
    INPUTS = "inputs"
    STATES = "states"
    SHARED_STORE = "shared_store"


@dataclass
class _MountedVolumesLocalPaths:
    outputs: Path
    inputs: Path
    states: tuple[Path, ...]
    shared_store: Path

    @classmethod
    def from_mounted_volumes(
        cls, mounted_volumes: MountedVolumes
    ) -> "_MountedVolumesLocalPaths":
        return cls(
            inputs=mounted_volumes.disk_inputs_path,
            outputs=mounted_volumes.disk_outputs_path,
            states=tuple(mounted_volumes.disk_state_paths()),
            shared_store=mounted_volumes.disk_shared_store_path,
        )

    def paths_from_volume_id(self, volume_id: VolumeID) -> list[Path]:
        result: Union[Path, tuple[Path, ...]] = self.__getattribute__(volume_id)
        if isinstance(result, Path):
            return [result]
        return list(result)


async def _create_file_with_user_wrote_only_permissions(file: Path) -> None:
    """only allows the user who created the files to change it"""
    # create empty file
    async with aiofiles.open(file, mode="w"):
        ...

    await chmod(file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)


async def create_hidden_file_on_all_volumes(mounted_volumes: MountedVolumes) -> None:
    # NOTE: by creating a hidden file on all mounted volumes
    # the same permissions are ensured and avoids
    # issues when starting the services

    volumes_local_paths = _MountedVolumesLocalPaths.from_mounted_volumes(
        mounted_volumes
    )
    for volume_path in volumes_local_paths.states + (
        volumes_local_paths.inputs,
        volumes_local_paths.outputs,
        volumes_local_paths.shared_store,
    ):
        hidden_file = volume_path / HIDDEN_FILE_NAME

        # restrict permissions
        await _create_file_with_user_wrote_only_permissions(hidden_file)

        # write content
        async with aiofiles.open(hidden_file, mode="w") as f:
            await f.write(
                f"Directory must not be empty.\nCreated by {__file__}.\n"
                "Required by oSPARC internals to properly enforce permissions on this "
                "directory and all its files"
            )


async def create_agent_file_on_all_volumes(mounted_volumes: MountedVolumes) -> None:
    volumes_local_paths = _MountedVolumesLocalPaths.from_mounted_volumes(
        mounted_volumes
    )

    # volumes which do not require saving
    for path in (volumes_local_paths.inputs, volumes_local_paths.shared_store):
        agent_file_path = path / AGENT_FILE_NAME
        await _create_file_with_user_wrote_only_permissions(agent_file_path)

        await save_volume_state(
            agent_file_path=agent_file_path,
            volume_state=VolumeState(requires_saving=False),
        )

    # volumes which require saving
    for path in volumes_local_paths.states + (volumes_local_paths.outputs,):
        agent_file_path = path / AGENT_FILE_NAME
        await _create_file_with_user_wrote_only_permissions(agent_file_path)

        await save_volume_state(
            agent_file_path=agent_file_path,
            volume_state=VolumeState(requires_saving=True, was_saved=False),
        )


async def set_volume_state(
    mounted_volumes: MountedVolumes,
    volume_id: VolumeID,
    requires_saving: bool,
    was_saved: Optional[bool],
) -> None:
    volumes_local_paths = _MountedVolumesLocalPaths.from_mounted_volumes(
        mounted_volumes
    )
    volume_paths: list[Path] = volumes_local_paths.paths_from_volume_id(volume_id)
    for volume_path in volume_paths:
        await save_volume_state(
            agent_file_path=volume_path / AGENT_FILE_NAME,
            volume_state=VolumeState(
                requires_saving=requires_saving, was_saved=was_saved
            ),
        )
