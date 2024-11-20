import functools
import logging
from typing import cast

from fastapi import FastAPI
from servicelib.logging_utils import log_context

from ..rabbitmq import get_rabbitmq_client
from ._models import SchedulePipelineRabbitMessage
from ._scheduler_base import BaseCompScheduler
from ._scheduler_factory import create_scheduler

_logger = logging.getLogger(__name__)


def _get_scheduler_worker(app: FastAPI) -> BaseCompScheduler:
    return cast(BaseCompScheduler, app.state.scheduler_worker)


async def _handle_distributed_pipeline(app: FastAPI, data: bytes) -> bool:

    with log_context(_logger, logging.DEBUG, msg="handling scheduling"):
        to_schedule_pipeline = SchedulePipelineRabbitMessage.parse_raw(data)
        await _get_scheduler_worker(app).schedule_pipeline(
            user_id=to_schedule_pipeline.user_id,
            project_id=to_schedule_pipeline.project_id,
            iteration=to_schedule_pipeline.iteration,
        )
        return True


async def setup_worker(app: FastAPI) -> None:
    rabbitmq_client = get_rabbitmq_client(app)
    await rabbitmq_client.subscribe(
        SchedulePipelineRabbitMessage.get_channel_name(),
        functools.partial(_handle_distributed_pipeline, app),
        exclusive_queue=False,
    )

    app.state.scheduler_worker = create_scheduler(app)


async def shutdown_worker(app: FastAPI) -> None:
    assert app.state.scheduler_worker  # nosec
    # TODO: we might need to cancel stuff here. not sure yet what
    # unsubscribing is maybe not a good idea if we want to keep the data in the queue
