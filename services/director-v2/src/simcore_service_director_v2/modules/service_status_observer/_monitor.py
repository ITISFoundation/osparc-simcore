from asyncio import Task
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from fastapi import FastAPI, status
from httpx import AsyncClient, HTTPError
from models_library.api_schemas_directorv2.dynamic_services_service import (
    RunningDynamicServiceDetails,
)
from models_library.projects_nodes_io import NodeID
from pydantic import NonNegativeFloat, NonNegativeInt, ValidationError
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.osparc_resource_manager import (
    OsparcResourceManager,
    OsparcResourceType,
    ResourceIdentifier,
)
from servicelib.utils import logged_gather

from ...meta import API_VTAG
from ..osparc_resource_tracker import get_osparc_resource_manager
from ._store import update_status_cache

_WAIT_FOR_TASK_TO_STOP: Final[NonNegativeFloat] = 5

SERVICES_STATUS_POLL_INTERVAL: Final[timedelta] = timedelta(seconds=60)
_PARALLEL_REQUESTS: Final[NonNegativeInt] = 5


@dataclass
class StatusesMonitor:
    app: FastAPI
    task: Task | None = None
    httpx_client = AsyncClient(base_url=f"http://localhost:8000/{API_VTAG}", timeout=5)

    async def _periodic_task(self) -> None:
        osparc_resoruce_manager: OsparcResourceManager = get_osparc_resource_manager(
            self.app
        )

        tracked_dynamic_services: set[
            ResourceIdentifier
        ] = await osparc_resoruce_manager.get_resources(
            OsparcResourceType.DYNAMIC_SERVICE
        )

        await logged_gather(
            *(self._update_status_cache(NodeID(x)) for x in tracked_dynamic_services),
            reraise=False,
            max_concurrency=_PARALLEL_REQUESTS,
        )

    async def _update_status_cache(self, node_id: NodeID) -> None:
        try:
            response = await self.httpx_client.get(f"/dynamic_services/{node_id}")
        except HTTPError:
            return

        if response.status_code != status.HTTP_200_OK:
            return

        with suppress(ValidationError):
            await update_status_cache(
                self.app, node_id, RunningDynamicServiceDetails.parse_raw(response.text)
            )

    async def startup(self) -> None:
        self.task = start_periodic_task(
            self._periodic_task,
            interval=SERVICES_STATUS_POLL_INTERVAL,
            task_name="statuses_monitor",
        )

    async def shutdown(self) -> None:
        if self.task:
            await stop_periodic_task(self.task, timeout=_WAIT_FOR_TASK_TO_STOP)


def setup_monitor(app: FastAPI):
    async def on_startup() -> None:
        app.state.statuses_monitor = statuses_monitor = StatusesMonitor(app=app)
        await statuses_monitor.startup()

    async def on_shutdown() -> None:
        statuses_store: StatusesMonitor = app.state.statuses_monitor
        await statuses_store.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
