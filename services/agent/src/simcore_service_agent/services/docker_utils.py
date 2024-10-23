import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

from aiodocker import DockerError
from aiodocker.docker import Docker
from aiodocker.volumes import DockerVolume
from fastapi import FastAPI
from models_library.api_schemas_directorv2.services import (
    CHARS_IN_VOLUME_NAME_BEFORE_DIR_NAME,
)
from servicelib.docker_constants import PREFIX_DYNAMIC_SIDECAR_VOLUMES
from servicelib.logging_utils import log_catch, log_context
from simcore_service_agent.core.settings import ApplicationSettings
from starlette import status

from ..models.volumes import VolumeDetails, VolumeDetailsAdapter
from .backup import backup_volume
from .instrumentation import get_instrumentation

_logger = logging.getLogger(__name__)


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
    """Returns all volumes unused by sidecars"""
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


async def get_volume_details(docker: Docker, *, volume_name: str) -> VolumeDetails:
    volume_details = await DockerVolume(docker, volume_name).show()
    return VolumeDetailsAdapter.validate_python(volume_details)


@contextmanager
def _log_volume_not_found(volume_name: str) -> Iterator[None]:
    try:
        yield
    except DockerError as e:
        if e.status == status.HTTP_404_NOT_FOUND:
            _logger.info("Volume not found '%s'", volume_name)
        else:
            raise


async def _backup_volume(app: FastAPI, docker: Docker, *, volume_name: str) -> None:
    """Backs up only volumes which require a backup"""
    if _does_volume_require_backup(volume_name):
        with log_context(
            _logger, logging.INFO, f"backup '{volume_name}'", log_duration=True
        ):
            volume_details = await get_volume_details(docker, volume_name=volume_name)
            settings: ApplicationSettings = app.state.settings
            get_instrumentation(app).agent_metrics.backedup_volumes(
                settings.AGENT_DOCKER_NODE_ID
            )
            await backup_volume(app, volume_details, volume_name)
    else:
        _logger.debug("No backup is required for '%s'", volume_name)


async def remove_volume(
    app: FastAPI, docker: Docker, *, volume_name: str, requires_backup: bool
) -> None:
    """Removes a volume and backs data up if required"""
    with log_context(
        _logger, logging.DEBUG, f"removing '{volume_name}'", log_duration=True
    ), log_catch(_logger, reraise=False), _log_volume_not_found(volume_name):
        if requires_backup:
            await _backup_volume(app, docker, volume_name=volume_name)

        await DockerVolume(docker, volume_name).delete()

        settings: ApplicationSettings = app.state.settings
        get_instrumentation(app).agent_metrics.remove_volumes(
            settings.AGENT_DOCKER_NODE_ID
        )
