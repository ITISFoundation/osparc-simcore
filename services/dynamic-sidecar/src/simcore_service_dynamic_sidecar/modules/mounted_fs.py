import os
from functools import cached_property
from pathlib import Path
from typing import AsyncGenerator, Generator, Iterator
from uuid import UUID

from fastapi import FastAPI
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings

from ..core.docker_utils import get_volume_by_label

DY_VOLUMES = Path("/dy-volumes")


def _ensure_path(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _name_from_full_path(path: Path) -> str:
    """transforms: /path/to/a/file -> _path_to_a_file"""
    return str(path).replace(os.sep, "_")


class MountedVolumes:
    """
    The inputs and outputs directories are created and by the dynamic-sidecar
    and mounted into all started containers at the specified path.

    Locally, on its disk, the dynamic-sidecar ensures the `inputs` and
    `outputs` directories are created in the external volume of name
    `dy-sidecar_UUID` in the `/dy-volumes` path.
    Eg: - /dy-sidecar_UUID_inputs:/inputs-dir
        - /dy-sidecar_UUID_outputs:/outputs-dir
    """

    def __init__(
        self,
        inputs_path: Path,
        outputs_path: Path,
        state_paths: list[Path],
        state_exclude: list[str],
        compose_namespace: str,
    ) -> None:
        self.inputs_path: Path = inputs_path
        self.outputs_path: Path = outputs_path
        self.state_paths: list[Path] = state_paths
        self.state_exclude: list[str] = state_exclude
        self.compose_namespace = compose_namespace

        self._ensure_directories()

    @cached_property
    def volume_name_inputs(self) -> str:
        """Same name as the namespace, to easily track components"""
        return f"{self.compose_namespace}{_name_from_full_path(self.inputs_path)}"

    @cached_property
    def volume_name_outputs(self) -> str:
        return f"{self.compose_namespace}{_name_from_full_path(self.outputs_path)}"

    def volume_name_state_paths(self) -> Generator[str, None, None]:
        for state_path in self.state_paths:
            yield f"{self.compose_namespace}{_name_from_full_path(state_path)}"

    @cached_property
    def disk_inputs_path(self) -> Path:
        return _ensure_path(DY_VOLUMES / self.inputs_path.relative_to("/"))

    @cached_property
    def disk_outputs_path(self) -> Path:
        return _ensure_path(DY_VOLUMES / self.outputs_path.relative_to("/"))

    def disk_state_paths(self) -> Iterator[Path]:
        for state_path in self.state_paths:
            yield _ensure_path(DY_VOLUMES / state_path.relative_to("/"))

    def all_disk_paths(self) -> Iterator[Path]:
        # PC: keeps iterator to follow same style as disk_state_paths but IMO it is overreaching
        yield self.disk_inputs_path
        yield self.disk_outputs_path
        yield from self.disk_state_paths()

    def _ensure_directories(self) -> None:
        """
        Creates the directories on its file system,
        these will be mounted elsewere.
        """
        _ensure_path(DY_VOLUMES)
        self.disk_inputs_path  # pylint:disable= pointless-statement
        self.disk_outputs_path  # pylint:disable= pointless-statement
        set(self.disk_state_paths())

    @staticmethod
    async def _get_bind_path_from_label(label: str, run_id: UUID) -> Path:
        volume_details = await get_volume_by_label(label=label, run_id=run_id)
        return Path(volume_details["Mountpoint"])

    async def get_inputs_docker_volume(self, run_id: UUID) -> str:
        bind_path: Path = await self._get_bind_path_from_label(
            self.volume_name_inputs, run_id
        )
        return f"{bind_path}:{self.inputs_path}"

    async def get_outputs_docker_volume(self, run_id: UUID) -> str:
        bind_path: Path = await self._get_bind_path_from_label(
            self.volume_name_outputs, run_id
        )
        return f"{bind_path}:{self.outputs_path}"

    async def iter_state_paths_to_docker_volumes(
        self, run_id: UUID
    ) -> AsyncGenerator[str, None]:
        for volume_state_path, state_path in zip(
            self.volume_name_state_paths(), self.state_paths
        ):
            bind_path: Path = await self._get_bind_path_from_label(
                volume_state_path, run_id
            )
            yield f"{bind_path}:{state_path}"


def setup_mounted_fs(app: FastAPI) -> MountedVolumes:
    settings: DynamicSidecarSettings = app.state.settings

    app.state.mounted_volumes = MountedVolumes(
        inputs_path=settings.DY_SIDECAR_PATH_INPUTS,
        outputs_path=settings.DY_SIDECAR_PATH_OUTPUTS,
        state_paths=settings.DY_SIDECAR_STATE_PATHS,
        state_exclude=settings.DY_SIDECAR_STATE_EXCLUDE,
        compose_namespace=settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE,
    )

    return app.state.mounted_volumes


__all__ = ["MountedVolumes"]
