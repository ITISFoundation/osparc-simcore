import functools
import logging
from typing import cast

from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.logging_utils import log_context

from ...utils.comp_scheduler import Iteration
from ..db import get_db_engine
from ..db.repositories.comp_runs import CompRunsRepository
from ..rabbitmq import get_rabbitmq_client
from ._models import SchedulePipelineRabbitMessage
from ._publisher import request_pipeline_scheduling
from ._scheduler_base import BaseCompScheduler
from ._scheduler_factory import create_scheduler

_logger = logging.getLogger(__name__)


def _empty_wake_up_callack(
    app: FastAPI, user_id: UserID, project_id: ProjectID, iteration: Iteration
) -> None:
    async def _async_cb():
        db_engine = get_db_engine(app)
        rabbit_mq_client = get_rabbitmq_client(app)
        comp_run = await CompRunsRepository.instance(db_engine).get(
            user_id=user_id, project_id=project_id, iteration=iteration
        )
        await request_pipeline_scheduling(comp_run, rabbit_mq_client, db_engine)


def _get_scheduler_worker(app: FastAPI) -> BaseCompScheduler:
    return cast(BaseCompScheduler, app.state.scheduler_worker)


async def _handle_distributed_pipeline(app: FastAPI, data: bytes) -> bool:

    with log_context(_logger, logging.DEBUG, msg="handling scheduling"):
        to_schedule_pipeline = SchedulePipelineRabbitMessage.parse_raw(data)
        get_rabbitmq_client(app).publish(
            SchedulePipelineRabbitMessage.get_channel_name(),
            to_schedule_pipeline,
        )
        await _get_scheduler_worker(app).schedule_pipeline(
            user_id=to_schedule_pipeline.user_id,
            project_id=to_schedule_pipeline.project_id,
            iteration=to_schedule_pipeline.iteration,
            wake_up_callback=_empty_wake_up_callack,
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
