import asyncio
import functools
import logging
from typing import cast

from fastapi import FastAPI
from servicelib.logging_utils import log_context
from servicelib.tracing import traced

from ..rabbitmq import get_rabbitmq_client
from ._constants import (
    TASK_RESULT_RELEASE_CONCURRENCY,
    TASK_RESULT_RELEASE_MAX_ATTEMPTS,
    TASK_RESULT_RELEASE_RETRY_DELAY,
)
from ._models import ReleaseTaskResultRabbitMessage
from ._scheduler_dask import DaskScheduler

_logger = logging.getLogger(__name__)


def _get_scheduler_worker(app: FastAPI) -> DaskScheduler:
    return cast(DaskScheduler, app.state.scheduler_worker)


@traced
async def _handle_release_task_result(app: FastAPI, data: bytes) -> bool:
    message = ReleaseTaskResultRabbitMessage.model_validate_json(data)
    with log_context(
        _logger,
        logging.DEBUG,
        msg=f"releasing task results for {message.job_ids}",
    ):
        # NOTE: let exceptions propagate: the rabbitmq client will nack and retry the
        # message (with backoff, up to a max number of attempts) instead of silently
        # dropping a failed release like the previous inline call used to.
        await _get_scheduler_worker(app).release_task_result(
            user_id=message.user_id,
            project_id=message.project_id,
            run_id=message.run_id,
            use_on_demand_clusters=message.use_on_demand_clusters,
            run_metadata=message.run_metadata,
            job_ids=message.job_ids,
        )
    return True


async def setup_releaser(app: FastAPI) -> None:
    rabbitmq_client = get_rabbitmq_client(app)
    app.state.task_result_releaser_consumers = await asyncio.gather(
        *(
            rabbitmq_client.subscribe(
                ReleaseTaskResultRabbitMessage.get_channel_name(),
                functools.partial(_handle_release_task_result, app),
                exclusive_queue=False,
                unexpected_error_retry_delay_s=TASK_RESULT_RELEASE_RETRY_DELAY.total_seconds(),
                unexpected_error_max_attempts=TASK_RESULT_RELEASE_MAX_ATTEMPTS,
            )
            for _ in range(TASK_RESULT_RELEASE_CONCURRENCY)
        )
    )


async def shutdown_releaser(app: FastAPI) -> None:
    rabbitmq_client = get_rabbitmq_client(app)
    await asyncio.gather(
        *(rabbitmq_client.unsubscribe_consumer(*consumer) for consumer in app.state.task_result_releaser_consumers),
        return_exceptions=False,
    )
