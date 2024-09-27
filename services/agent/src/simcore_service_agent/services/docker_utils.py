import logging
from typing import Final

from aiodocker import DockerError
from aiodocker.docker import Docker
from aiodocker.volumes import DockerVolume
from fastapi import FastAPI
from models_library.api_schemas_directorv2.services import (
    CHARS_IN_VOLUME_NAME_BEFORE_DIR_NAME,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import RunID
from models_library.users import UserID
from pydantic import BaseModel, Field
from servicelib.docker_constants import PREFIX_DYNAMIC_SIDECAR_VOLUMES
from servicelib.logging_utils import log_catch, log_context
from starlette import status

from .backup_manager import backup_volume

_logger = logging.getLogger(__name__)


class DynamicServiceVolumeLabel(BaseModel):
    node_uuid: NodeID
    run_id: RunID
    source: str
    study_id: ProjectID
    swarm_stack_name: str
    user_id: UserID

    @property
    def directory_name(self) -> str:
        return self.source[CHARS_IN_VOLUME_NAME_BEFORE_DIR_NAME:][::-1].strip("_")


class VolumeDetails(BaseModel):
    mountpoint: str = Field(alias="Mountpoint")
    labels: DynamicServiceVolumeLabel = Field(alias="Labels")


def _reverse_string(to_reverse: str) -> str:
    return to_reverse[::-1]


_VOLUMES_NOT_TO_BACKUP: Final[tuple[str, ...]] = (
    _reverse_string("inputs"),
    _reverse_string("shared-store"),
)


def _does_volume_require_backup(volume_name: str) -> bool:
    # from    `dyv_1726228407_891aa1a7-eb31-459f-8aed-8c902f5f5fb0_dd84f39e-7154-4a13-ba1d-50068d723104_stupni_www_`
    # retruns `stupni_www_`
    inverse_name_part = volume_name[CHARS_IN_VOLUME_NAME_BEFORE_DIR_NAME:]
    return not inverse_name_part.startswith(_VOLUMES_NOT_TO_BACKUP)


async def get_unused_dynamc_sidecar_volumes(docker: Docker) -> set[str]:
    """Returns all unused volumes that are dropped by sidecars"""
    volumes = await docker.volumes.list()
    all_volumes: set[str] = {volume["Name"] for volume in volumes["Volumes"]}

    containers = await docker.containers.list(all=True)

    used_volumes: set[str] = set()
    for container in containers:
        container_info = await container.show()
        mounts = container_info.get("Mounts", [])
        for mount in mounts:
            if mount["Type"] == "volume":
                used_volumes.add(mount["Name"])

    unused_volumes = all_volumes - used_volumes
    return {v for v in unused_volumes if v.startswith(PREFIX_DYNAMIC_SIDECAR_VOLUMES)}


async def _backup_volume(app: FastAPI, *, volume_name: str) -> None:
    """Backs up only volumes which require a backup"""
    if _does_volume_require_backup(volume_name):
        with log_context(
            _logger, logging.INFO, f"backup '{volume_name}'", log_duration=True
        ):
            await backup_volume(app, volume_name)
    else:
        _logger.debug("No backup is required for '%s'", volume_name)


async def remove_volume(
    app: FastAPI, docker: Docker, *, volume_name: str, requires_backup: bool
) -> None:
    """Removes a volume and backs data up if required"""
    with log_context(
        _logger, logging.DEBUG, f"removing '{volume_name}'", log_duration=True
    ):
        if requires_backup:
            await _backup_volume(app, volume_name=volume_name)
        with log_catch(_logger, reraise=False):
            try:
                await DockerVolume(docker, volume_name).delete()
            except DockerError as e:
                if e.status == status.HTTP_404_NOT_FOUND:
                    _logger.info("Volume not found '%s'", volume_name)
                else:
                    raise


async def get_volume_details(docker: Docker, *, volume_name: str) -> VolumeDetails:
    volume_details = await DockerVolume(docker, volume_name).show()
    return VolumeDetails.parse_obj(volume_details)
