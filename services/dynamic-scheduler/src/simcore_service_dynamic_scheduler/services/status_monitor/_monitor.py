import logging
from datetime import timedelta
from functools import cached_property
from typing import Final

import arrow
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from pydantic import NonNegativeFloat, NonNegativeInt
from servicelib.utils import logged_gather

from ..service_tracker import (
    NORMAL_RATE_POLL_INTERVAL,
    TrackedServiceModel,
    get_all_tracked,
    remove_tracked,
    set_scheduled_to_run,
)
from ..service_tracker._models import SchedulerServiceState, UserRequestedState
from ._deferred_get_status import DeferredGetStatus

_logger = logging.getLogger(__name__)

_MAX_CONCURRENCY: Final[NonNegativeInt] = 10


async def _start_get_status_deferred(
    app: FastAPI, node_id: NodeID, *, next_check_delay: timedelta
) -> None:
    await set_scheduled_to_run(app, node_id, next_check_delay)
    await DeferredGetStatus.start(node_id=node_id)


class Monitor:
    def __init__(self, app: FastAPI, status_worker_interval: timedelta) -> None:
        self.app = app
        self.status_worker_interval = status_worker_interval

    @cached_property
    def status_worker_interval_seconds(self) -> NonNegativeFloat:
        return self.status_worker_interval.total_seconds()

    async def _worker_start_get_status_requests(self) -> None:
        # NOTE: this worker runs on only once across all instances of the scheduler

        models: dict[NodeID, TrackedServiceModel] = await get_all_tracked(self.app)

        to_remove: list[NodeID] = []
        to_start: list[NodeID] = []

        current_timestamp = arrow.utcnow().timestamp()

        for node_id, model in models.items():
            # check if service is idle and status polling should stop
            if (
                model.current_state == SchedulerServiceState.IDLE
                and model.requested_sate == UserRequestedState.STOPPED
            ):
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
        await logged_gather(
            *(remove_tracked(self.app, node_id) for node_id in to_remove),
            max_concurrency=_MAX_CONCURRENCY,
        )

        _logger.debug("Poll status for tracked services: '%s'", to_start)
        await logged_gather(
            *(
                _start_get_status_deferred(
                    self.app, node_id, next_check_delay=NORMAL_RATE_POLL_INTERVAL
                )
                for node_id in to_start
            ),
            max_concurrency=_MAX_CONCURRENCY,
        )

    async def setup(self) -> None:
        # TODO: run uniquely across all processes
        pass

    async def shutdown(self) -> None:
        pass
