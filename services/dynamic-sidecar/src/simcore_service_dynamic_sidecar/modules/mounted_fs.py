import itertools
import os
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator
from uuid import UUID

from fastapi import FastAPI
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings

from ..core.docker_utils import get_volume_by_label


@dataclass
class VolumeMountInfo:
    name: str  # name used for external volume
    # TODO: consider renaming. Create a narrative around.
    # Here the source is not in the host but as seen by the sidecar
    # at the same time this is not
    # Using same naming as in https://docs.docker.com/compose/compose-file/#volumes
    source: Path  # path seen by sidecar
    target: Path  # path seen by target container (car!)

    @classmethod
    def create_from(cls, target_dir: Path, compose_namespace: str, base_dir: Path):
        # normalizes into /path/to/a/file -> _path_to_a_file
        # TODO: why this important!?
        name_suffix = f"{target_dir}".replace(os.sep, "_")
        mount = cls(
            source=base_dir / target_dir.relative_to("/"),
            target=target_dir,
            name=f"{compose_namespace}{name_suffix}",
        )

        mount.source.mkdir(parents=True, exist_ok=True)
        assert mount.source.is_dir()  # nosec
        return mount


class MountedVolumes:
    """
    TODO: PC->ANE doc properly

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
        inputs_dir: Path,
        outputs_dir: Path,
        state_dirs: list[Path],
        state_exclude: list[str],
        compose_namespace: str,
        common_basedir: Path,
    ):
        for dir1, dir2 in itertools.product(
            [inputs_dir, outputs_dir] + state_dirs, repeat=2
        ):
            if dir1 != dir2 and dir1 in dir2.parents:
                raise ValueError("'{dir1}' folder not allowed inside '{dir2}' folder")

        self._inputs_volume = VolumeMountInfo.create_from(
            inputs_dir, compose_namespace, common_basedir
        )
        self._outputs_volume = VolumeMountInfo.create_from(
            outputs_dir, compose_namespace, common_basedir
        )
        self._state_volumes = [
            VolumeMountInfo.create_from(state_path, compose_namespace, common_basedir)
            for state_path in state_dirs
        ]

        self.state_exclude = state_exclude

    # TODO: all these properties can be replaced by self.inputs_volume ...
    @property
    def volume_name_inputs(self) -> str:
        """Same name as the namespace, to easily track components"""
        return self._inputs_volume.name

    @property
    def volume_name_outputs(self) -> str:
        return self._outputs_volume.name

    @property
    def volume_names_for_states(self) -> list[str]:
        return [s.name for s in self._state_volumes]

    @property
    def disk_inputs_path(self) -> Path:
        return self._inputs_volume.source

    @property
    def disk_outputs_path(self) -> Path:
        return self._outputs_volume.source

    @property
    def disk_state_paths(self) -> list[Path]:
        return [s.source for s in self._state_volumes]

    @property
    def all_disk_paths(self) -> list[Path]:
        return [self.disk_inputs_path, self.disk_outputs_path] + self.disk_state_paths

    # VOLUME BINDS: mountpoint:target

    @staticmethod
    async def _get_volume_mountpoint(label: str, run_id: UUID) -> Path:
        """
        Returns disk's path to mount point

        E.g. /var/lib/docker/volumes/684ee68d26d651d0d0a051e711d63f75d952cd2d9cf6a7ea094742f21e7d5adc/_data
        """
        volume = await get_volume_by_label(label=label, run_id=run_id)
        return volume.mountpoint

    async def get_inputs_docker_volume(self, run_id: UUID) -> str:
        bind_path: Path = await self._get_volume_mountpoint(
            self._inputs_volume.name, run_id
        )
        return f"{bind_path}:{self._inputs_volume.target}"

    async def get_outputs_docker_volume(self, run_id: UUID) -> str:
        bind_path: Path = await self._get_volume_mountpoint(
            self._outputs_volume.name, run_id
        )
        return f"{bind_path}:{self._outputs_volume.target}"

    async def iter_state_paths_to_docker_volumes(
        self, run_id: UUID
    ) -> AsyncIterator[str]:
        for state_volume in self._state_volumes:
            bind_path: Path = await self._get_volume_mountpoint(
                state_volume.name, run_id
            )
            yield f"{bind_path}:{state_volume.target}"


def setup_mounted_fs(app: FastAPI) -> MountedVolumes:
    settings: DynamicSidecarSettings = app.state.settings

    app.state.mounted_volumes = MountedVolumes(
        inputs_dir=settings.DY_SIDECAR_PATH_INPUTS,
        outputs_dir=settings.DY_SIDECAR_PATH_OUTPUTS,
        state_dirs=settings.DY_SIDECAR_STATE_PATHS,
        state_exclude=settings.DY_SIDECAR_STATE_EXCLUDE,
        compose_namespace=settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE,
        common_basedir=settings.DYNAMIC_SIDECAR_DY_VOLUMES_COMMON_DIR,
    )

    return app.state.mounted_volumes


__all__: tuple[str, ...] = ("MountedVolumes",)
