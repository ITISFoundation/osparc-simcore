# pylint:disable=no-self-use

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from aiodocker import Docker
from aiodocker.types import JSONObject
from fastapi import FastAPI
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStop,
)
from pydantic import NonNegativeInt
from servicelib.logging_utils import log_context
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.services import (
    stop_dynamic_service,
)
from simcore_sdk.node_ports_common.r_clone_mount import (
    DelegateInterface,
    FilesInTransfer,
    MountActivity,
    RCloneMountManager,
)

from ..core.rabbitmq import get_rabbitmq_rpc_client, post_sidecar_log_message
from ..core.settings import ApplicationSettings
from ..modules.mounted_fs import MountedVolumes

_logger = logging.getLogger(__name__)


_EXPECTED_BIND_PATHS_COUNT: Final[NonNegativeInt] = 2


@dataclass
class _MountActivitySummary:
    path: Path
    files_queued: int
    files_in_transfer: FilesInTransfer


@asynccontextmanager
async def _get_docker_client() -> AsyncIterator[Docker]:
    async with Docker() as client:
        yield client


class DynamicSidecarRCloneMountDelegate(DelegateInterface):
    def __init__(self, app: FastAPI, settings: ApplicationSettings, mounted_volumes: MountedVolumes) -> None:
        self.app = app
        self.settings = settings
        self.mounted_volumes = mounted_volumes

    async def requires_data_mounting(self) -> bool:
        return self.settings.DY_SIDECAR_REQUIRES_DATA_MOUNTING

    async def _get_vfs_paths(self) -> tuple[Path, Path]:
        vfs_cache_path = await self.mounted_volumes.get_vfs_cache_docker_volume(self.settings.DY_SIDECAR_RUN_ID)

        vfs_source, vfs_target = (
            f"{vfs_cache_path}".replace(f"{self.settings.DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR}", "")
        ).split(":")

        return Path(vfs_source), Path(vfs_target)

    async def get_local_vfs_cache_path(self) -> Path:
        _, vfs_target = await self._get_vfs_paths()
        return self.settings.DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR / vfs_target.relative_to("/")

    async def get_bind_paths(self, state_path: Path) -> list:
        vfs_source, vfs_target = await self._get_vfs_paths()

        bind_paths: list[dict] = [
            {
                "Type": "bind",
                "Source": f"{vfs_source}",
                "Target": f"{vfs_target}",
                "BindOptions": {"Propagation": "rshared"},
            }
        ]

        state_path_no_dy_volume = state_path.relative_to(self.settings.DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR)
        matcher = f":/{state_path_no_dy_volume}"

        async for entry in self.mounted_volumes.iter_state_paths_to_docker_volumes(self.settings.DY_SIDECAR_RUN_ID):
            if entry.endswith(matcher):
                mount_str = entry.replace(f"/{state_path_no_dy_volume}", f"{state_path}")
                source, target = mount_str.split(":")
                bind_paths.append(
                    {
                        "Type": "bind",
                        "Source": source,
                        "Target": target,
                        "BindOptions": {"Propagation": "rshared"},
                    }
                )
                break

        if len(bind_paths) != _EXPECTED_BIND_PATHS_COUNT:
            msg = f"Could not resolve volume path for {state_path}"
            raise RuntimeError(msg)

        return bind_paths

    async def mount_activity(self, state_path: Path, activity: MountActivity) -> None:
        # Frontend should receive and use this message to provide feedback to the user
        # regarding the mount activity
        summary = _MountActivitySummary(
            path=state_path, files_queued=len(activity.queued), files_in_transfer=activity.in_transfer
        )
        _logger.info("Mount activity %s", summary)

    async def request_shutdown(self) -> None:
        client = get_rabbitmq_rpc_client(self.app)

        with log_context(_logger, logging.INFO, "requesting service shutdown via dynamic-scheduler"):
            await stop_dynamic_service(
                client,
                dynamic_service_stop=DynamicServiceStop(
                    user_id=self.settings.DY_SIDECAR_USER_ID,
                    project_id=self.settings.DY_SIDECAR_PROJECT_ID,
                    node_id=self.settings.DY_SIDECAR_NODE_ID,
                    simcore_user_agent="",
                    save_state=True,
                ),
            )
            await post_sidecar_log_message(
                self.app,
                (
                    "Your service was closed due to an issue that would create unexpected behavior. "
                    "No data was lost. Thank you for your understanding."
                ),
                log_level=logging.WARNING,
            )

    async def create_container(self, config: JSONObject, name: str) -> None:
        async with _get_docker_client() as client:
            await client.containers.run(config=config, name=name)

    async def container_inspect(self, container_name: str) -> dict[str, Any]:
        async with _get_docker_client() as client:
            existing_container = await client.containers.get(container_name)
            return await existing_container.show()

    async def remove_container(self, container_name: str) -> None:
        async with _get_docker_client() as client:
            existing_container = await client.containers.get(container_name)
            await existing_container.delete(force=True)


def setup_r_clone_mount_manager(app: FastAPI):
    async def _on_startup() -> None:
        settings: ApplicationSettings = app.state.settings
        mounted_volumes: MountedVolumes = app.state.mounted_volumes

        app.state.r_clone_mount_manager = r_clone_mount_manager = RCloneMountManager(
            settings.DY_SIDECAR_R_CLONE_SETTINGS,
            delegate=DynamicSidecarRCloneMountDelegate(app, settings, mounted_volumes),
        )
        await r_clone_mount_manager.setup()

    async def _on_shutdown() -> None:
        r_clone_mount_manager: RCloneMountManager = app.state.r_clone_mount_manager
        await r_clone_mount_manager.teardown()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


def get_r_clone_mount_manager(app: FastAPI) -> RCloneMountManager:
    assert isinstance(app.state.r_clone_mount_manager, RCloneMountManager)  # nosec
    return app.state.r_clone_mount_manager
