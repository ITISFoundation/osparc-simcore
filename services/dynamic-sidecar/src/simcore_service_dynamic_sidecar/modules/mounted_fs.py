import os
from collections.abc import AsyncGenerator, Generator, Iterator
from functools import cached_property
from pathlib import Path

from fastapi import FastAPI
from models_library.projects_nodes import NodeID
from models_library.services import RunID
from servicelib.docker_constants import PREFIX_DYNAMIC_SIDECAR_VOLUMES

from ..core.docker_utils import get_volume_by_label
from ..core.settings import ApplicationSettings


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
        run_id: RunID,
        node_id: NodeID,
        inputs_path: Path,
        outputs_path: Path,
        user_preferences_path: Path | None,
        state_paths: list[Path],
        state_exclude: set[str],
        compose_namespace: str,
        dy_volumes: Path,
    ) -> None:
        self.run_id: RunID = run_id
        self.node_id: NodeID = node_id
        self.inputs_path: Path = inputs_path
        self.outputs_path: Path = outputs_path
        self.user_preferences_path = user_preferences_path
        self.state_paths: list[Path] = state_paths
        self.state_exclude: set[str] = state_exclude
        self.compose_namespace = compose_namespace
        self._dy_volumes = dy_volumes

        self._ensure_directories()

    @cached_property
    def volume_name_inputs(self) -> str:
        """Same name as the namespace, to easily track components"""
        return (
            f"{PREFIX_DYNAMIC_SIDECAR_VOLUMES}_{self.run_id}_{self.node_id}"
            f"_{_name_from_full_path(self.inputs_path)[::-1]}"
        )

    @cached_property
    def volume_name_outputs(self) -> str:
        return (
            f"{PREFIX_DYNAMIC_SIDECAR_VOLUMES}_{self.run_id}_{self.node_id}"
            f"_{_name_from_full_path(self.outputs_path)[::-1]}"
        )

    @cached_property
    def volume_user_preferences(self) -> str | None:
        if self.user_preferences_path is None:
            return None
        return (
            f"{PREFIX_DYNAMIC_SIDECAR_VOLUMES}_{self.run_id}_{self.node_id}"
            f"_{_name_from_full_path(self.user_preferences_path)[::-1]}"
        )

    def volume_name_state_paths(self) -> Generator[str, None, None]:
        for state_path in self.state_paths:
            yield (
                f"{PREFIX_DYNAMIC_SIDECAR_VOLUMES}_{self.run_id}_{self.node_id}"
                f"_{_name_from_full_path(state_path)[::-1]}"
            )

    @cached_property
    def disk_inputs_path(self) -> Path:
        return _ensure_path(self._dy_volumes / self.inputs_path.relative_to("/"))

    @cached_property
    def disk_outputs_path(self) -> Path:
        return _ensure_path(self._dy_volumes / self.outputs_path.relative_to("/"))

    def disk_state_paths_iter(self) -> Iterator[Path]:
        for state_path in self.state_paths:
            yield _ensure_path(self._dy_volumes / state_path.relative_to("/"))

    def all_disk_paths_iter(self) -> Iterator[Path]:
        # PC: keeps iterator to follow same style as disk_state_paths but IMO it is overreaching
        yield self.disk_inputs_path
        yield self.disk_outputs_path
        yield from self.disk_state_paths_iter()

    def _ensure_directories(self) -> None:
        """
        Creates directories on its file system, these will be mounted by the user services.
        """
        _ensure_path(self._dy_volumes)
        for path in self.all_disk_paths_iter():
            _ensure_path(path)

    @staticmethod
    async def _get_bind_path_from_label(label: str, run_id: RunID) -> Path:
        volume_details = await get_volume_by_label(label=label, run_id=run_id)
        return Path(volume_details["Mountpoint"])

    async def get_inputs_docker_volume(self, run_id: RunID) -> str:
        bind_path: Path = await self._get_bind_path_from_label(
            self.volume_name_inputs, run_id
        )
        return f"{bind_path}:{self.inputs_path}"

    async def get_outputs_docker_volume(self, run_id: RunID) -> str:
        bind_path: Path = await self._get_bind_path_from_label(
            self.volume_name_outputs, run_id
        )
        return f"{bind_path}:{self.outputs_path}"

    async def get_user_preferences_path_volume(self, run_id: RunID) -> str | None:
        if self.volume_user_preferences is None:
            return None

        bind_path: Path = await self._get_bind_path_from_label(
            self.volume_user_preferences, run_id
        )
        return f"{bind_path}:{self.user_preferences_path}"

    async def iter_state_paths_to_docker_volumes(
        self, run_id: RunID
    ) -> AsyncGenerator[str, None]:
        for volume_state_path, state_path in zip(
            self.volume_name_state_paths(), self.state_paths, strict=True
        ):
            bind_path: Path = await self._get_bind_path_from_label(
                volume_state_path, run_id
            )
            yield f"{bind_path}:{state_path}"


def setup_mounted_fs(app: FastAPI) -> MountedVolumes:
    settings: ApplicationSettings = app.state.settings

    app.state.mounted_volumes = MountedVolumes(
        run_id=settings.DY_SIDECAR_RUN_ID,
        node_id=settings.DY_SIDECAR_NODE_ID,
        inputs_path=settings.DY_SIDECAR_PATH_INPUTS,
        outputs_path=settings.DY_SIDECAR_PATH_OUTPUTS,
        user_preferences_path=settings.DY_SIDECAR_USER_PREFERENCES_PATH,
        state_paths=settings.DY_SIDECAR_STATE_PATHS,
        state_exclude=settings.DY_SIDECAR_STATE_EXCLUDE,
        compose_namespace=settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE,
        dy_volumes=settings.DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR,
    )

    return app.state.mounted_volumes
