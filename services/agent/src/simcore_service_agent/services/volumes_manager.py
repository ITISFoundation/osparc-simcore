import logging
from asyncio import Lock, Task
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Final

import arrow
from aiodocker.docker import Docker
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from pydantic import NonNegativeFloat
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.logging_utils import log_context
from servicelib.rabbitmq.rpc_interfaces.agent.errors import (
    NoServiceVolumesFoundRPCError,
)
from tenacity import AsyncRetrying, before_sleep_log, stop_after_delay, wait_fixed

from ..core.settings import ApplicationSettings
from .docker_utils import get_unused_dynamc_sidecar_volumes, remove_volume

_logger = logging.getLogger(__name__)

_WAIT_FOR_UNUSED_SERVICE_VOLUMES: Final[timedelta] = timedelta(minutes=1)


@dataclass
class VolumesManager(  # pylint:disable=too-many-instance-attributes
    SingletonInAppStateMixin
):
    app: FastAPI
    book_keeping_interval: timedelta
    volume_cleanup_interval: timedelta
    remove_volumes_inactive_for: NonNegativeFloat

    docker: Docker = field(default_factory=Docker)
    removal_lock: Lock = field(default_factory=Lock)

    _task_bookkeeping: Task | None = None
    _unused_volumes: dict[str, datetime] = field(default_factory=dict)

    _task_periodic_volume_cleanup: Task | None = None

    app_state_name: str = "volumes_manager"

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
        # also avoids issues with accessing the docker API in parallel
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

    async def _wait_for_service_volumes_to_become_unused(
        self, node_id: NodeID
    ) -> set[str]:
        # NOTE: it usually takes a few seconds for volumes to become unused,
        # if agent does not wait for this operation to finish,
        # volumes will be removed and backed up by the background task
        # causing unncecessary data transfer to S3
        async for attempt in AsyncRetrying(
            reraise=True,
            stop=stop_after_delay(_WAIT_FOR_UNUSED_SERVICE_VOLUMES.total_seconds()),
            wait=wait_fixed(1),
            before_sleep=before_sleep_log(_logger, logging.DEBUG),
        ):
            with attempt:
                current_unused_volumes = await get_unused_dynamc_sidecar_volumes(
                    self.docker
                )

                service_volumes = {
                    v for v in current_unused_volumes if f"{node_id}" in v
                }
                _logger.debug(
                    "service %s found volumes to remove: %s", node_id, service_volumes
                )
                if len(service_volumes) == 0:
                    raise NoServiceVolumesFoundRPCError(
                        period=_WAIT_FOR_UNUSED_SERVICE_VOLUMES.total_seconds(),
                        node_id=node_id,
                    )

        return service_volumes

    async def remove_service_volumes(self, node_id: NodeID) -> None:
        # bookkept volumes might not be up to date
        service_volumes = await self._wait_for_service_volumes_to_become_unused(node_id)
        _logger.debug(
            "will remove volumes for %s from service_volumes=%s",
            node_id,
            service_volumes,
        )

        for volume_name in service_volumes:
            # volumes already saved to S3 by the sidecar and no longer require backup
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
    return VolumesManager.get_from_app_state(app)


def setup_volume_manager(app: FastAPI) -> None:
    async def _on_startup() -> None:
        settings: ApplicationSettings = app.state.settings

        volumes_manager = VolumesManager(
            app=app,
            book_keeping_interval=settings.AGENT_VOLUMES_CLEANUP_BOOK_KEEPING_INTERVAL,
            volume_cleanup_interval=settings.AGENT_VOLUMES_CLEANUP_INTERVAL,
            remove_volumes_inactive_for=settings.AGENT_VOLUMES_CLEANUP_REMOVE_VOLUMES_INACTIVE_FOR.total_seconds(),
        )
        volumes_manager.set_to_app_state(app)
        await volumes_manager.setup()

    async def _on_shutdown() -> None:
        await VolumesManager.get_from_app_state(app).shutdown()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
