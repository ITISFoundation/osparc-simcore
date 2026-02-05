import logging
from asyncio import Task, create_task
from datetime import timedelta
from typing import Final

from common_library.async_tools import cancel_wait_task
from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from models_library.services_enums import ServiceState
from pydantic import NonNegativeInt
from servicelib.background_task_utils import exclusive_periodic
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.logging_utils import log_catch
from servicelib.redis._utils import handle_redis_returns_union_types
from servicelib.utils import limited_gather

from ..common_interface import get_service_status
from ..redis import RedisDatabase, get_redis_client
from ._lifecycle_protocol import SupportsLifecycle
from ._models import SchedulerServiceStatus

_logger = logging.getLogger(__name__)

_PREFIX: Final[str] = "pss"
_STATUS: Final[str] = "s"
_TRACKING: Final[str] = "tracked-services"
_PERIODIC_HANDLING_MESSAGE: Final[str] = "Periodic check handled by app_id="


async def _get_scheduler_service_status(app: FastAPI, node_id: NodeID) -> SchedulerServiceStatus:
    """Remaps platform service status to something that the scheduler understands"""
    service_status: NodeGet | DynamicServiceGet | NodeGetIdle = await get_service_status(app, node_id=node_id)

    if isinstance(service_status, NodeGetIdle):
        return SchedulerServiceStatus.IS_ABSENT

    state: ServiceState = (
        service_status.state if isinstance(service_status, DynamicServiceGet) else service_status.service_state
    )

    match state:
        case ServiceState.IDLE | ServiceState.COMPLETE:
            return SchedulerServiceStatus.IS_ABSENT
        case ServiceState.RUNNING:
            return SchedulerServiceStatus.IS_PRESENT
        case ServiceState.PENDING | ServiceState.PULLING | ServiceState.STARTING:
            return SchedulerServiceStatus.TRANSITION_TO_PRESENT
        case ServiceState.STOPPING:
            return SchedulerServiceStatus.TRANSITION_TO_ABSENT
        case ServiceState.FAILED:
            return SchedulerServiceStatus.IN_ERROR

    msg = f"Unhandled service {state=} for {service_status=}"
    raise NotImplementedError(msg)


def _get_service_key(node_id: NodeID) -> str:
    return f"{_PREFIX}:{_STATUS}:{node_id}"


def _get_tracking_key() -> str:
    return f"{_PREFIX}:{_TRACKING}"


class _RedisInterface:
    def __init__(self, app: FastAPI) -> None:
        self._redis = get_redis_client(app, RedisDatabase.DYNAMIC_SERVICES).redis

    async def get_status(self, node_id: NodeID) -> SchedulerServiceStatus | None:
        result = await self._redis.get(_get_service_key(node_id))
        return None if result is None else SchedulerServiceStatus(result.decode())

    async def set_status(self, node_id: NodeID, status: SchedulerServiceStatus, *, ttl_milliseconds: int) -> None:
        await self._redis.set(_get_service_key(node_id), status, px=ttl_milliseconds)

    async def track(self, *node_ids: NodeID) -> None:
        if len(node_ids) == 0:
            return
        await handle_redis_returns_union_types(self._redis.sadd(_get_tracking_key(), *[f"{x}" for x in node_ids]))

    async def untrack(self, *node_ids: NodeID) -> None:
        if len(node_ids) == 0:
            return
        await handle_redis_returns_union_types(self._redis.srem(_get_tracking_key(), *[f"{x}" for x in node_ids]))

    async def get_all_tracked(self) -> set[NodeID]:
        return {NodeID(result.decode()) async for result in self._redis.sscan_iter(_get_tracking_key())}


_NAME: Final[str] = "scheduler_status_manager"


_MAX_CONCURRENCY: Final[NonNegativeInt] = 10


class StatusManager(SingletonInAppStateMixin, SupportsLifecycle):
    app_state_name: str = f"p_{_NAME}"

    def __init__(self, app: FastAPI, *, status_ttl: timedelta, update_statuses_interval: timedelta) -> None:
        self.app = app
        self.redis_interface = _RedisInterface(app)
        self._ttl_ms = int(status_ttl.total_seconds() * 1000)
        self.update_statuses_interval = update_statuses_interval

        self._task_scheduler_service_status: Task | None = None

    async def set_tracked_services(self, to_track: set[NodeID]) -> None:
        # NOTE: This must be called periodically after querying the DB table for currently tracked services
        # (UserRequests requested.PRESENT).
        currently_tracked = await self.redis_interface.get_all_tracked()

        to_add = to_track - currently_tracked
        to_remove = currently_tracked - to_track

        await self.redis_interface.track(*to_add)
        await self.redis_interface.untrack(*to_remove)

    async def get_scheduler_service_status(self, node_id: NodeID) -> SchedulerServiceStatus:
        status = await self.redis_interface.get_status(node_id)
        if status is not None:
            return status

        _logger.info("Status for node '%s' not found in redis cache, recovering directly from platform", node_id)
        return await _get_scheduler_service_status(self.app, node_id)

    async def _safe_service_status_update(self, node_id: NodeID) -> None:
        with log_catch(_logger, reraise=False):
            status = await _get_scheduler_service_status(self.app, node_id)
            await self.redis_interface.set_status(node_id, status, ttl_milliseconds=self._ttl_ms)

    async def _worker_update_scheduler_service_status(self) -> None:
        tracked_services = await self.redis_interface.get_all_tracked()
        await limited_gather(
            *(self._safe_service_status_update(node_id) for node_id in tracked_services),
            limit=_MAX_CONCURRENCY,
            log=_logger,
        )

    async def setup(self) -> None:
        @exclusive_periodic(
            get_redis_client(self.app, RedisDatabase.LOCKS),
            task_interval=self.update_statuses_interval,
            retry_after=self.update_statuses_interval,
        )
        async def _periodic_check_services_require_status_update() -> None:
            _logger.debug("%s='%s'", _PERIODIC_HANDLING_MESSAGE, id(self))
            await self._worker_update_scheduler_service_status()

        self._task_scheduler_service_status = create_task(
            _periodic_check_services_require_status_update(), name=f"periodic_{_NAME}"
        )

    async def shutdown(self) -> None:
        if self._task_scheduler_service_status is not None:
            await cancel_wait_task(self._task_scheduler_service_status)
