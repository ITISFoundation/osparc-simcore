import datetime
import logging
from asyncio import Task
from typing import Final

from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from pydantic import NonNegativeInt
from servicelib.background_task import stop_periodic_task
from servicelib.logging_utils import log_context
from servicelib.redis import RedisClientSDK
from servicelib.redis_utils import start_exclusive_periodic_task
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
        check_interval: datetime.timedelta = datetime.timedelta(seconds=5),
    ) -> None:
        super().__init__(app, redis_client_sdk)

        self.check_interval = check_interval
        self.service_status_cache: ServiceStatusCache = ServiceStatusCache(
            app,
            ttl=self.check_interval.total_seconds() * 4,
            namespace="services_tracker",
        )

        self._check_task: Task | None = None

    async def setup(self) -> None:
        await super().setup()

        self._check_task = start_exclusive_periodic_task(
            self._redis_client_sdk,
            self._check_services_status_task,
            task_period=self.check_interval,
            task_name=f"{self.class_path()}_check_services_status_task",
        )

    async def shutdown(self) -> None:
        if self._check_task:
            await stop_periodic_task(self._check_task, timeout=5)

        await super().shutdown()

    async def _check_single_service(self, node_id: NodeID) -> None:
        service_status = await self.get(identifier=node_id)
        if service_status is None:
            _logger.debug("Could not retrieve the status of services %s", node_id)
            return

        cache_key = f"{node_id}"
        cached_status = await self.service_status_cache.get_value(cache_key)
        await self.service_status_cache.set_value(cache_key, service_status)

        if cached_status is None or cached_status != service_status:
            cleanup_context = await self._get_identifier_context(node_id)
            assert cleanup_context  # nosec

            await publish_message(
                self.app,
                node_id=node_id,
                service_status=service_status,
                user_id=cleanup_context.user_id,
            )

    async def _check_services_status_task(self) -> None:
        # runs at regular intervals on one single worker and enqueues requests
        with log_context(_logger, logging.INFO, "check services status"):
            await logged_gather(
                *(
                    self._check_single_service(node_id)
                    for node_id in await self._get_tracked()
                ),
                max_concurrency=_DIRECTOR_V2_API_PARALLELISM,
            )
