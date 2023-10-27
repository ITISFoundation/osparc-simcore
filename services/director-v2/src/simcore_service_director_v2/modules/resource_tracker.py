from asyncio import Task
from datetime import timedelta
from typing import Final

from fastapi import FastAPI, status
from httpx import AsyncClient
from models_library.api_schemas_directorv2.dynamic_services_service import (
    RunningDynamicServiceDetails,
)
from pydantic import NonNegativeFloat, ValidationError
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.osparc_resource_manager import (
    BaseResourceHandler,
    OsparcResourceManager,
    OsparcResourceType,
    ResourceIdentifier,
)
from servicelib.redis import RedisClientSDK

from ..meta import API_VTAG
from .redis import get_redis_client_sdk

_REMOVE_NOT_PRESENT_SERVICES_INTERVAL: Final[timedelta] = timedelta(seconds=60)
_STOP_TASK_TIMEOUT_S: Final[NonNegativeFloat] = 5


# pylint: disable=abstract-method
class DynamicServicesHandler(BaseResourceHandler):
    # NOTE: only used to check if a service is present in oSPARC

    def __init__(self) -> None:
        self.httpx_client = AsyncClient(base_url=f"http://localhost:8000/{API_VTAG}")

    async def is_present(self, identifier: ResourceIdentifier) -> bool:
        response = await self.httpx_client.get(f"/dynamic_services/{identifier}")

        if response.status_code != status.HTTP_200_OK:
            return False

        try:
            RunningDynamicServiceDetails.parse_raw(response.text)
            return True
        except ValidationError:
            return False


class DirectorV2OsparcResourceManager(OsparcResourceManager):
    _task: Task | None = None

    async def _remove_un_tracked_tasks_task(self) -> None:
        await self.remove_resources_which_are_no_longer_present(
            OsparcResourceType.DYNAMIC_SERVICE
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
        ) = DirectorV2OsparcResourceManager(redis_client_sdk)

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
