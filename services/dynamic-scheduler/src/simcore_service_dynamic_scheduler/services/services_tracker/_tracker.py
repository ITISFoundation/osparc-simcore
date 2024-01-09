import json
import logging
from asyncio import Task
from typing import Final

from fastapi import FastAPI
from pydantic import NonNegativeFloat, NonNegativeInt
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.redis import RedisClientSDK
from servicelib.redis_utils import exclusive
from servicelib.utils import logged_gather

from ._notifier import publish_message
from ._resource_manager import ServicesManager
from ._status_cache import ServiceStatusCache

_DIRECTOR_V2_API_PARALLELISM: Final[NonNegativeInt] = 10

_logger = logging.getLogger(__name__)


class ServicesTracker(ServicesManager):
    def __init__(
        self,
        app: FastAPI,
        redis_client_sdk: RedisClientSDK,
        check_interval: NonNegativeFloat = 10,
    ) -> None:
        super().__init__(app, redis_client_sdk)

        self.check_interval = check_interval
        self.service_status_cache: ServiceStatusCache = ServiceStatusCache(
            app, ttl=self.check_interval * 4, namespace="services_tracker"
        )

        self._check_task: Task | None = None

    async def setup(self) -> None:
        await super().setup()

        lock_key = f"lock:{self.class_path()}:services-tracker"
        lock_value = json.dumps({})
        self._check_task = start_periodic_task(
            exclusive(self._redis_client_sdk, lock_key=lock_key, lock_value=lock_value)(
                self._check_services_status_task
            ),
            interval=self.cleanup_interval,
            task_name=f"{self.class_path()}_check_services_status_task",
        )

    async def shutdown(self) -> None:
        if self._check_task:
            await stop_periodic_task(self._check_task, timeout=5)

        await super().shutdown()

    async def _check_single_service(self, node_id) -> None:
        service_status = await self.get(identifier=node_id)
        if service_status is None:
            _logger.info("Could not retrieve the status of services %s", node_id)
            return

        cached_status = await self.service_status_cache.get_value(f"{node_id}")
        await self.service_status_cache.set_value(f"{node_id}", service_status)

        if cached_status is None:
            await publish_message(
                self.app, node_id=node_id, service_status=service_status
            )
            return

        if service_status != cached_status:
            await publish_message(
                self.app, node_id=node_id, service_status=service_status
            )

    async def _check_services_status_task(self) -> None:
        await logged_gather(
            *(
                self._check_single_service(node_id)
                for node_id in await self._get_tracked()
            ),
            max_concurrency=_DIRECTOR_V2_API_PARALLELISM,
        )
