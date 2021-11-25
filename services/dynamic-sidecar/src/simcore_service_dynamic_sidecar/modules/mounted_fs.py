import os
from functools import cached_property
from pathlib import Path
from typing import Generator, List, Optional

from simcore_service_dynamic_sidecar.core.settings import (
    DynamicSidecarSettings,
    get_settings,
)

DY_VOLUMES = Path("/dy-volumes")

_mounted_volumes: Optional["MountedVolumes"] = None


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
        self, inputs_path: Path, outputs_path: Path, state_paths: List[Path]
    ) -> None:
        self.inputs_path: Path = inputs_path
        self.outputs_path: Path = outputs_path
        self.state_paths: List[Path] = state_paths

        self._ensure_directories()

    @cached_property
    def volume_name_inputs(self) -> str:
        """Same name as the namespace, to easily track components"""
        compose_namespace = get_settings().DYNAMIC_SIDECAR_COMPOSE_NAMESPACE
        return f"{compose_namespace}{_name_from_full_path(self.inputs_path)}"

    @cached_property
    def volume_name_outputs(self) -> str:
        compose_namespace = get_settings().DYNAMIC_SIDECAR_COMPOSE_NAMESPACE
        return f"{compose_namespace}{_name_from_full_path(self.outputs_path)}"

    def volume_name_state_paths(self) -> Generator[str, None, None]:
        compose_namespace = get_settings().DYNAMIC_SIDECAR_COMPOSE_NAMESPACE
        for state_path in self.state_paths:
            yield f"{compose_namespace}{_name_from_full_path(state_path)}"

    @cached_property
    def disk_inputs_path(self) -> Path:
        return _ensure_path(DY_VOLUMES / self.inputs_path.relative_to("/"))

    @cached_property
    def disk_outputs_path(self) -> Path:
        return _ensure_path(DY_VOLUMES / self.outputs_path.relative_to("/"))

    def disk_state_paths(self) -> Generator[Path, None, None]:
        for state_path in self.state_paths:
            yield _ensure_path(DY_VOLUMES / state_path.relative_to("/"))

    def _ensure_directories(self) -> None:
        """
        Creates the directories on its file system,
        these will be mounted elsewere.
        """
        _ensure_path(DY_VOLUMES)
        self.disk_inputs_path  # pylint:disable= pointless-statement
        self.disk_outputs_path  # pylint:disable= pointless-statement
        set(self.disk_state_paths())

    def get_inputs_docker_volume(self) -> str:
        return f"{self.volume_name_inputs}:{self.inputs_path}"

    def get_outputs_docker_volume(self) -> str:
        return f"{self.volume_name_outputs}:{self.outputs_path}"

    def get_state_paths_docker_volumes(self) -> Generator[str, None, None]:
        for volume_state_path, state_path in zip(
            self.volume_name_state_paths(), self.state_paths
        ):
            yield f"{volume_state_path}:{state_path}"


def setup_mounted_fs() -> MountedVolumes:
    global _mounted_volumes  # pylint: disable=global-statement

    settings: DynamicSidecarSettings = get_settings()

    _mounted_volumes = MountedVolumes(
        inputs_path=settings.DY_SIDECAR_PATH_INPUTS,
        outputs_path=settings.DY_SIDECAR_PATH_OUTPUTS,
        state_paths=settings.DY_SIDECAR_STATE_PATHS,
    )

    return _mounted_volumes


def get_mounted_volumes() -> MountedVolumes:
    if _mounted_volumes is None:
        raise RuntimeError(
            f"{MountedVolumes.__name__} was not initialized, did not call setup"
        )
    return _mounted_volumes


__all__ = ["get_mounted_volumes", "MountedVolumes"]
