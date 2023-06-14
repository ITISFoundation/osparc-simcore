from fastapi import FastAPI

from ..core.settings import ApplicationSettings
from .docker import docker_client, get_dyv_volumes
from .volumes_cleanup import get_sidecar_volumes_list, remove_sidecar_volumes
from .volumes_cleanup.models import SidecarVolumes, VolumeDict


async def task_cleanup_volumes(app: FastAPI) -> None:
    settings: ApplicationSettings = app.state.settings

    async with docker_client() as client:
        dyv_volumes: list[VolumeDict] = await get_dyv_volumes(
            client, settings.AGENT_VOLUMES_CLEANUP_TARGET_SWARM_STACK_NAME
        )
        if len(dyv_volumes) == 0:
            return

        sidecar_volumes: list[SidecarVolumes] = get_sidecar_volumes_list(dyv_volumes)
        await remove_sidecar_volumes(app, sidecar_volumes)
