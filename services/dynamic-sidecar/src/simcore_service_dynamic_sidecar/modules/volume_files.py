import asyncio
import os
import stat
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import AsyncIterator

import aiofiles
from aiofiles import os as aiofiles_os
from models_library.volumes import VolumeCategory
from pydantic import PositiveFloat
from servicelib.file_constants import AGENT_FILE_NAME, HIDDEN_FILE_NAME
from servicelib.volumes_utils import VolumeState, VolumeStatus, save_volume_state

from ..core.utils import async_command
from .mounted_fs import MountedVolumes

chmod = aiofiles_os.wrap(os.chmod)  # type: ignore


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

    def paths_from_volume_category(self, volume_category: VolumeCategory) -> list[Path]:
        result: Path | tuple[Path, ...] = self.__getattribute__(volume_category.lower())
        if isinstance(result, Path):
            return [result]
        return list(result)


async def _toggle_file_immutability(
    file_path: Path, set_immutable: bool, timeout: PositiveFloat = 5
) -> None:
    immutable: str = "+i" if set_immutable else "-i"
    await async_command(f"chattr {immutable} {file_path}", timeout=timeout)


async def _create_file_with_restricted_permissions(file_path: Path) -> None:
    """only allows the user who created the files to change it"""

    # NOTE: the `stat.S_IWGRP`, group write permission, should not be here.
    # when the user services start they chown and chmod and all the existing
    # files in the work directory.
    # For now this is required otherwise the dynamic-sidecar will not be able to
    # write back the created file any longer.

    file_touch = partial(
        file_path.touch,
        mode=(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH),
        exist_ok=True,
    )
    await asyncio.get_event_loop().run_in_executor(None, file_touch)

    # File is set immutable (it will only be changed by this process)
    await _toggle_file_immutability(file_path=file_path, set_immutable=True)


@asynccontextmanager
async def _disable_file_immutability(file_path: Path) -> AsyncIterator[None]:
    await _toggle_file_immutability(file_path=file_path, set_immutable=True)
    try:
        yield None
    finally:
        await _toggle_file_immutability(file_path=file_path, set_immutable=False)


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
        await _create_file_with_restricted_permissions(hidden_file)

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
        await _create_file_with_restricted_permissions(agent_file_path)
        async with _disable_file_immutability(agent_file_path):
            await save_volume_state(
                agent_file_path=agent_file_path,
                volume_state=VolumeState(status=VolumeStatus.CONTENT_NO_SAVE_REQUIRED),
            )

    # volumes which require saving
    for path in volumes_local_paths.states + (volumes_local_paths.outputs,):
        agent_file_path = path / AGENT_FILE_NAME
        await _create_file_with_restricted_permissions(agent_file_path)

        async with _disable_file_immutability(agent_file_path):
            await save_volume_state(
                agent_file_path=agent_file_path,
                volume_state=VolumeState(status=VolumeStatus.CONTENT_NEEDS_TO_BE_SAVED),
            )


async def set_volume_state(
    mounted_volumes: MountedVolumes,
    volume_category: VolumeCategory,
    status: VolumeStatus,
) -> None:
    volumes_local_paths = _MountedVolumesLocalPaths.from_mounted_volumes(
        mounted_volumes
    )
    volume_paths: list[Path] = volumes_local_paths.paths_from_volume_category(
        volume_category
    )
    for volume_path in volume_paths:
        agent_file_path = volume_path / AGENT_FILE_NAME
        async with _disable_file_immutability(agent_file_path):
            await save_volume_state(
                agent_file_path=agent_file_path, volume_state=VolumeState(status=status)
            )
