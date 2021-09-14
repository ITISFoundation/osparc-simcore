from functools import cached_property
from pathlib import Path
from typing import Optional

from simcore_service_dynamic_sidecar.core.settings import (
    DynamicSidecarSettings,
    get_settings,
)

DY_VOLUMES = Path("/dy-volumes")

_mounted_paths: Optional["MountedVolumes"] = None


def _ensure_path(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


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

    def __init__(self, inputs_path: Path, outputs_path: Path) -> None:
        self.inputs_path: Path = inputs_path
        self.outputs_path: Path = outputs_path

    @cached_property
    def volume_name_inputs(self) -> str:
        """Same name as the namespace, to easily track components"""
        compose_namespace = get_settings().DYNAMIC_SIDECAR_COMPOSE_NAMESPACE
        return f"{compose_namespace}_inputs"

    @cached_property
    def volume_name_outputs(self) -> str:
        compose_namespace = get_settings().DYNAMIC_SIDECAR_COMPOSE_NAMESPACE
        return f"{compose_namespace}_outputs"

    @cached_property
    def disk_inputs_path(self) -> Path:
        return _ensure_path(DY_VOLUMES / "inputs")

    @cached_property
    def disk_outputs_path(self) -> Path:
        return _ensure_path(DY_VOLUMES / "outputs")

    def ensure_directories(self) -> None:
        """
        Creates the directories on its file system, these will be mounted
        elsewere.
        """
        _ensure_path(DY_VOLUMES)
        self.disk_inputs_path  # pylint:disable= pointless-statement
        self.disk_outputs_path  # pylint:disable= pointless-statement

    def get_inputs_docker_volume(self) -> str:
        return f"{self.volume_name_inputs}:{self.inputs_path}"

    def get_outputs_docker_volume(self) -> str:
        return f"{self.volume_name_outputs}:{self.outputs_path}"


def setup_mounted_fs() -> MountedVolumes:
    global _mounted_paths  # pylint: disable=global-statement

    settings: DynamicSidecarSettings = get_settings()

    _mounted_paths = MountedVolumes(
        inputs_path=settings.DY_SIDECAR_PATH_INPUTS,
        outputs_path=settings.DY_SIDECAR_PATH_OUTPUTS,
    )
    _mounted_paths.ensure_directories()

    return _mounted_paths


def get_mounted_volumes() -> MountedVolumes:
    global _mounted_paths  # pylint: disable=global-statement
    if _mounted_paths is None:
        raise RuntimeError(
            f"{MountedVolumes.__name__} was not initialized, did not call setup"
        )
    return _mounted_paths


__all__ = ["get_mounted_volumes", "MountedVolumes"]
