import logging
from dataclasses import dataclass, field
from types import TracebackType
from typing import Final

from aiodocker.docker import Docker
from aiodocker.volumes import DockerVolume
from fastapi import FastAPI
from servicelib.docker_constants import PREFIX_DYNAMIC_SIDECAR_VOLUMES
from servicelib.logging_utils import log_context

_logger = logging.getLogger(__name__)


def _reverse_string(to_reverse: str) -> str:
    return to_reverse[::-1]


_VOLUMES_NOT_TO_BACKUP: Final[tuple[str, ...]] = (
    _reverse_string("inputs"),
    _reverse_string("shared-store"),
)


def _does_volume_require_backup(volume_name: str) -> bool:
    # from `dyv_1726228407_891aa1a7-eb31-459f-8aed-8c902f5f5fb0_dd84f39e-7154-4a13-ba1d-50068d723104_stupni_www_`
    # get  `stupni_www_`
    inverse_name_part = volume_name[89:]
    return not inverse_name_part.startswith(_VOLUMES_NOT_TO_BACKUP)


@dataclass
class VolumeManager:
    _docker: Docker = field(default_factory=Docker)

    async def close(self) -> None:
        await self._docker.close()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def __aenter__(self) -> "VolumeManager":
        return self

    async def get_unused_dynamc_sidecar_volumes(self) -> set[str]:
        volumes = await self._docker.volumes.list()
        all_volumes: set[str] = {volume["Name"] for volume in volumes["Volumes"]}

        containers = await self._docker.containers.list(all=True)

        used_volumes: set[str] = set()
        for container in containers:
            container_info = await container.show()
            mounts = container_info.get("Mounts", [])
            for mount in mounts:
                if mount["Type"] == "volume":
                    used_volumes.add(mount["Name"])

        unused_volumes = all_volumes - used_volumes
        return {
            v for v in unused_volumes if v.startswith(PREFIX_DYNAMIC_SIDECAR_VOLUMES)
        }

    async def remove_volume(self, volume_name: str) -> None:
        with log_context(
            _logger, logging.INFO, f"removing {volume_name}", log_duration=True
        ):
            await DockerVolume(self._docker, volume_name).delete()

    async def backup_volume(self, volume_name: str) -> None:
        if _does_volume_require_backup(volume_name):
            # log backing up in info
            with log_context(
                _logger, logging.INFO, f"backup {volume_name}", log_duration=True
            ):
                pass
        else:
            # log skipping backup in debug
            _logger.debug("No backup is required for %s", volume_name)


def get_service_volume_manager(app: FastAPI) -> VolumeManager:
    service_volume_manager: VolumeManager = app.state.service_volume_manager
    return service_volume_manager


def setup_service_volume_manager(app: FastAPI) -> None:
    async def _on_startup() -> None:
        app.state.service_volume_manager = VolumeManager()

    async def _on_shutdown() -> None:
        service_volume_manager: VolumeManager = app.state.service_volume_manager
        await service_volume_manager.close()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
