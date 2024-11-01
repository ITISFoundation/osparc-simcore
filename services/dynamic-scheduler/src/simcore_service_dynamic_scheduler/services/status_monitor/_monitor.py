import logging
from datetime import timedelta
from functools import cached_property
from typing import Final

import arrow
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from pydantic import NonNegativeFloat, NonNegativeInt
from servicelib.background_task import stop_periodic_task
from servicelib.redis_utils import start_exclusive_periodic_task
from servicelib.utils import limited_gather
from settings_library.redis import RedisDatabase

from .. import service_tracker
from ..redis import get_redis_client
from ..service_tracker import NORMAL_RATE_POLL_INTERVAL, TrackedServiceModel
from ..service_tracker._models import SchedulerServiceState, UserRequestedState
from ._deferred_get_status import DeferredGetStatus

_logger = logging.getLogger(__name__)

_INTERVAL_BETWEEN_CHECKS: Final[timedelta] = timedelta(seconds=1)
_MAX_CONCURRENCY: Final[NonNegativeInt] = 10

_REMOVE_AFTER_IDLE_FOR: Final[timedelta] = timedelta(minutes=5)


async def _start_get_status_deferred(
    app: FastAPI, node_id: NodeID, *, next_check_delay: timedelta
) -> None:
    await service_tracker.set_service_scheduled_to_run(app, node_id, next_check_delay)
    await DeferredGetStatus.start(node_id=node_id)


def _can_be_removed(model: TrackedServiceModel) -> bool:

    # requested **as** `STOPPED`
    # service **reports** `IDLE`
    if (
        model.current_state == SchedulerServiceState.IDLE
        and model.requested_state == UserRequestedState.STOPPED
    ):
        return True

    # NOTE: currently dynamic-scheduler does nto automatically start a
    # service reported who's requested_state is STARTED
    # to avoid monitoring services which no longer exist,
    # the service has to be removed.

    # requested as `STARTED`
    # service **reports** `IDLE` since `_REMOVE_AFTER_IDLE_FOR`
    if (  # noqa: SIM103
        model.current_state == SchedulerServiceState.IDLE
        and model.requested_state == UserRequestedState.RUNNING
        and arrow.utcnow().timestamp() - model.last_state_change
        > _REMOVE_AFTER_IDLE_FOR.total_seconds()
    ):
        return True

    return False


class Monitor:
    def __init__(self, app: FastAPI, status_worker_interval: timedelta) -> None:
        self.app = app
        self.status_worker_interval = status_worker_interval

    @cached_property
    def status_worker_interval_seconds(self) -> NonNegativeFloat:
        return self.status_worker_interval.total_seconds()

    async def _worker_start_get_status_requests(self) -> None:
        """
        Check if a service requires it's status to be polled.
        Note that the interval at which the status is polled can vary.
        This is a relatively low resource check.
        """

        # NOTE: this worker runs on only once across all instances of the scheduler

        models: dict[
            NodeID, TrackedServiceModel
        ] = await service_tracker.get_all_tracked_services(self.app)

        to_remove: list[NodeID] = []
        to_start: list[NodeID] = []

        current_timestamp = arrow.utcnow().timestamp()

        for node_id, model in models.items():
            if _can_be_removed(model):
                to_remove.append(node_id)
                continue

            job_not_running = not (
                model.scheduled_to_run
                and model.service_status_task_uid is not None
                and await DeferredGetStatus.is_present(model.service_status_task_uid)
            )
            wait_period_finished = current_timestamp > model.check_status_after
            if job_not_running and wait_period_finished:
                to_start.append(node_id)
            else:
                _logger.info(
                    "Skipping status check for %s, because: %s or %s",
                    node_id,
                    f"{job_not_running=}",
                    (
                        f"{wait_period_finished=}"
                        if wait_period_finished
                        else f"can_start_in={model.check_status_after - current_timestamp}"
                    ),
                )

        _logger.debug("Removing tracked services: '%s'", to_remove)
        await limited_gather(
            *(
                service_tracker.remove_tracked_service(self.app, node_id)
                for node_id in to_remove
            ),
            limit=_MAX_CONCURRENCY,
        )

        _logger.debug("Poll status for tracked services: '%s'", to_start)
        await limited_gather(
            *(
                _start_get_status_deferred(
                    self.app, node_id, next_check_delay=NORMAL_RATE_POLL_INTERVAL
                )
                for node_id in to_start
            ),
            limit=_MAX_CONCURRENCY,
        )

    async def setup(self) -> None:
        self.app.state.status_monitor_background_task = start_exclusive_periodic_task(
            get_redis_client(self.app, RedisDatabase.LOCKS),
            self._worker_start_get_status_requests,
            task_period=_INTERVAL_BETWEEN_CHECKS,
            retry_after=_INTERVAL_BETWEEN_CHECKS,
            task_name="periodic_service_status_update",
        )

    async def shutdown(self) -> None:
        if getattr(self.app.state, "status_monitor_background_task", None):
            await stop_periodic_task(self.app.state.status_monitor_background_task)
