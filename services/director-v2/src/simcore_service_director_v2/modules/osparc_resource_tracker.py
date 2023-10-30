from asyncio import Task
from datetime import timedelta
from typing import Final

from fastapi import FastAPI
from httpx import AsyncClient
from models_library.projects_nodes_io import NodeID
from pydantic import NonNegativeFloat, NonNegativeInt
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.osparc_resource_manager import (
    BaseResourceHandler,
    OsparcResourceManager,
    OsparcResourceType,
    ResourceIdentifier,
)
from servicelib.redis import RedisClientSDK
from servicelib.utils import logged_gather

from ..meta import API_VTAG
from .redis import get_redis_client_sdk
from .service_status_observer import remove_from_status_cache
from .utils import get_service_status

_REMOVE_NOT_PRESENT_SERVICES_INTERVAL: Final[timedelta] = timedelta(seconds=60)
_STOP_TASK_TIMEOUT_S: Final[NonNegativeFloat] = 5
_MAX_PARALLEL_REQUESTS: Final[NonNegativeInt] = 5


# pylint: disable=abstract-method
class DynamicServicesHandler(BaseResourceHandler):
    # NOTE: only used to check if a service is present in oSPARC

    def __init__(self) -> None:
        self.httpx_client = AsyncClient(base_url=f"http://localhost:8000/{API_VTAG}")

    async def is_present(self, identifier: ResourceIdentifier) -> bool:
        return (
            await get_service_status(self.httpx_client, NodeID(identifier)) is not None
        )


class DirectorV2OsparcResourceManager(OsparcResourceManager):
    def __init__(self, app: FastAPI, redis_client_sdk: RedisClientSDK) -> None:
        super().__init__(redis_client_sdk)

        self.app = app
        self._task: Task | None = None

    async def _remove_un_tracked_tasks_task(self) -> None:
        removed_identifiers: set[
            ResourceIdentifier
        ] = await self.remove_resources_which_are_no_longer_present(
            OsparcResourceType.DYNAMIC_SERVICE
        )
        await logged_gather(
            *(
                remove_from_status_cache(self.app, NodeID(x))
                for x in removed_identifiers
            ),
            max_concurrency=_MAX_PARALLEL_REQUESTS,
        )

    async def setup(self) -> None:
        self._task = start_periodic_task(
            self._remove_un_tracked_tasks_task,
            interval=_REMOVE_NOT_PRESENT_SERVICES_INTERVAL,
            task_name="remove_not_present_services",
        )

    async def shutdown(self) -> None:
        if self._task:
            await stop_periodic_task(self._task, timeout=_STOP_TASK_TIMEOUT_S)


def setup(app: FastAPI):
    async def on_startup() -> None:
        redis_client_sdk: RedisClientSDK = get_redis_client_sdk(app)

        app.state.osparc_resource_manager = (
            osparc_resource_manager
        ) = DirectorV2OsparcResourceManager(redis_client_sdk=redis_client_sdk, app=app)

        osparc_resource_manager.register(
            OsparcResourceType.DYNAMIC_SERVICE,
            resource_handler=DynamicServicesHandler(),
        )
        await osparc_resource_manager.setup()

    async def on_shutdown() -> None:
        osparc_resource_manager: (
            DirectorV2OsparcResourceManager
        ) = app.state.osparc_resource_manager
        await osparc_resource_manager.setup()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_osparc_resource_manager(app: FastAPI) -> OsparcResourceManager:
    return app.state.osparc_resource_manager
