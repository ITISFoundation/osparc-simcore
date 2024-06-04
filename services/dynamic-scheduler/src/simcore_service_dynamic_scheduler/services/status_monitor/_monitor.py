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
    TrackedServiceModel,
    get_all_tracked,
    set_check_status_after_to,
)
from ._deferred_get_status import DeferredGetStatus

_logger = logging.getLogger(__name__)

_MAX_CONCURRENCY: Final[NonNegativeInt] = 10


class Monitor:
    def __init__(self, app: FastAPI, check_threshold: timedelta) -> None:
        self.app = app
        self.check_threshold = check_threshold

    @cached_property
    def check_threshold_seconds(self) -> NonNegativeFloat:
        return self.check_threshold.total_seconds()

    async def _worker_start_get_status_requests(self) -> None:
        # NOTE: this worker runs on only once across all instances of the scheduler

        models: dict[NodeID, TrackedServiceModel] = await get_all_tracked(self.app)

        to_start: list[NodeID] = []
        to_set_check_status_after: list[NodeID] = []

        current_timestamp = arrow.utcnow().timestamp()

        for node_id, model in models.items():
            if (
                model.check_status_after is None
                or model.check_status_after > current_timestamp
            ):
                # status fetching is required
                if model.service_status_task_uid is None:
                    to_start.append(node_id)
                else:
                    _logger.info(
                        "Skipping status check for %s, since already running. Will check later",
                        node_id,
                    )
            if model.check_status_after is None:
                to_set_check_status_after.append(node_id)

        # for services where the check never ran, make sure we are nto able to start the check while it's running
        await logged_gather(
            *(
                set_check_status_after_to(self.app, node_id, timedelta(seconds=5))
                for node_id in to_set_check_status_after
            ),
            max_concurrency=_MAX_CONCURRENCY,
        )

        await logged_gather(
            *(DeferredGetStatus.start(node_id=node_id) for node_id in to_start),
            max_concurrency=_MAX_CONCURRENCY,
        )

    async def setup(self) -> None:
        # TODO: start uniquely running task
        # NOTE: THIS needs to be distributed only 1 at a time
        pass

    async def shutdown(self) -> None:
        pass
