import logging
from asyncio import Lock, Task
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import arrow
from aiodocker.docker import Docker
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from pydantic import NonNegativeFloat
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.logging_utils import log_context

from ..core.settings import ApplicationSettings
from .docker_utils import get_unused_dynamc_sidecar_volumes, remove_volume

_logger = logging.getLogger(__name__)


@dataclass
class VolumesManager:
    app: FastAPI
    book_keeping_interval: timedelta
    volume_cleanup_interval: timedelta
    remove_volumes_inactive_for: NonNegativeFloat

    docker: Docker = field(default_factory=Docker)
    removal_lock: Lock = field(default_factory=Lock)

    _task_bookkeeping: Task | None = None
    _unused_volumes: dict[str, datetime] = field(default_factory=dict)

    _task_periodic_volume_cleanup: Task | None = None

    async def setup(self) -> None:
        self._task_bookkeeping = start_periodic_task(
            self._bookkeeping_task,
            interval=self.book_keeping_interval,
            task_name="volumes bookkeeping",
        )
        self._task_periodic_volume_cleanup = start_periodic_task(
            self._bookkeeping_task,
            interval=self.volume_cleanup_interval,
            task_name="volume cleanup",
        )

    async def shutdown(self) -> None:
        await self.docker.close()

        if self._task_bookkeeping:
            await stop_periodic_task(self._task_bookkeeping)

        if self._task_periodic_volume_cleanup:
            await stop_periodic_task(self._task_periodic_volume_cleanup)

    async def _bookkeeping_task(self) -> None:
        with log_context(_logger, logging.DEBUG, "volume bookkeeping"):
            current_unused_volumes = await get_unused_dynamc_sidecar_volumes(
                self.docker
            )
            old_unused_volumes = set(self._unused_volumes.keys())

            # remove
            to_remove = old_unused_volumes - current_unused_volumes
            for volume in to_remove:
                self._unused_volumes.pop(volume, None)

            # volumes which have just been detected as inactive
            to_add = current_unused_volumes - old_unused_volumes
            for volume in to_add:
                self._unused_volumes[volume] = arrow.utcnow().datetime

    async def _remove_volume_safe(
        self, *, volume_name: str, requires_backup: bool
    ) -> None:
        # NOTE: to avoid race conditions only one volume can be removed
        # also avoids issues withaccessing the docker API in parallel for volume removal on this node
        async with self.removal_lock:
            await remove_volume(
                self.app,
                self.docker,
                volume_name=volume_name,
                requires_backup=requires_backup,
            )

    async def _periodic_volmue_cleanup_task(self) -> None:
        with log_context(_logger, logging.DEBUG, "volume cleanup"):
            volumes_to_remove: set[str] = set()
            for volume_name, inactive_since in self._unused_volumes.items():
                volume_inactive_sicne = (
                    arrow.utcnow().datetime - inactive_since
                ).total_seconds()
                if volume_inactive_sicne > self.remove_volumes_inactive_for:
                    volumes_to_remove.add(volume_name)

            for volume in volumes_to_remove:
                await self._remove_volume_safe(volume_name=volume, requires_backup=True)

    async def remove_service_volumes(self, node_id: NodeID) -> None:
        # bookkept volumes might not be up to date
        current_unused_volumes = await get_unused_dynamc_sidecar_volumes(self.docker)

        service_volumes: set[str] = set()
        for volume in current_unused_volumes:
            if f"{node_id}" in volume:
                service_volumes.add(volume)

        for volume_name in service_volumes:
            # these volumes have already been saved to S3 by the sidecar, no longer requires a backup
            await self._remove_volume_safe(
                volume_name=volume_name, requires_backup=False
            )

    async def remove_all_volumes(self) -> None:
        # bookkept volumes might not be up to date
        current_unused_volumes = await get_unused_dynamc_sidecar_volumes(self.docker)

        with log_context(_logger, logging.INFO, "remove all volumes"):
            for volume in current_unused_volumes:
                await self._remove_volume_safe(volume_name=volume, requires_backup=True)


def get_volumes_manager(app: FastAPI) -> VolumesManager:
    volumes_manager: VolumesManager = app.state.volumes_manager
    return volumes_manager


def setup_volume_manager(app: FastAPI) -> None:
    async def _on_startup() -> None:
        settings: ApplicationSettings = app.state.settings

        volumes_manager = app.state.volumes_manager = VolumesManager(
            app=app,
            book_keeping_interval=settings.AGENT_VOLUMES_CLENUP_BOOK_KEEPING_INTERVAL,
            volume_cleanup_interval=settings.AGENT_VOLUMES_CLEANUP_INTERVAL,
            remove_volumes_inactive_for=settings.AGENT_VOLUMES_CLENUP_REMOVE_VOLUMES_INACTIVE_FOR.total_seconds(),
        )
        await volumes_manager.setup()

    async def _on_shutdown() -> None:
        volumes_manager: VolumesManager = app.state.volumes_manager
        await volumes_manager.shutdown()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
