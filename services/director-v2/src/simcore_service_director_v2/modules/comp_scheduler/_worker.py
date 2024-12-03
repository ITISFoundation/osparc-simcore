import asyncio
import contextlib
import functools
import logging
from typing import cast

from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.logging_utils import log_context
from servicelib.redis import CouldNotAcquireLockError
from servicelib.redis_utils import exclusive

from ...core.settings import get_application_settings
from ...models.comp_runs import Iteration
from ..rabbitmq import get_rabbitmq_client
from ._constants import MODULE_NAME_WORKER
from ._models import SchedulePipelineRabbitMessage
from ._scheduler_base import BaseCompScheduler
from ._scheduler_factory import create_scheduler
from ._utils import get_redis_client_from_app, get_redis_lock_key

_logger = logging.getLogger(__name__)


def _get_scheduler_worker(app: FastAPI) -> BaseCompScheduler:
    return cast(BaseCompScheduler, app.state.scheduler_worker)


def _unique_key_builder(
    _app, user_id: UserID, project_id: ProjectID, iteration: Iteration
) -> str:
    return f"{user_id}:{project_id}:{iteration}"


@exclusive(
    redis=get_redis_client_from_app,
    lock_key=get_redis_lock_key(
        MODULE_NAME_WORKER, unique_lock_key_builder=_unique_key_builder
    ),
)
async def _exclusively_schedule_pipeline(
    app: FastAPI, *, user_id: UserID, project_id: ProjectID, iteration: Iteration
) -> None:
    await _get_scheduler_worker(app).apply(
        user_id=user_id,
        project_id=project_id,
        iteration=iteration,
    )


async def _handle_apply_distributed_schedule(app: FastAPI, data: bytes) -> bool:

    with log_context(_logger, logging.DEBUG, msg="handling scheduling"):
        to_schedule_pipeline = SchedulePipelineRabbitMessage.model_validate_json(data)
        with contextlib.suppress(CouldNotAcquireLockError):
            await _exclusively_schedule_pipeline(
                app,
                user_id=to_schedule_pipeline.user_id,
                project_id=to_schedule_pipeline.project_id,
                iteration=to_schedule_pipeline.iteration,
            )
        return True


async def setup_worker(app: FastAPI) -> None:
    app_settings = get_application_settings(app)
    rabbitmq_client = get_rabbitmq_client(app)
    app.state.scheduler_worker_consumers = await asyncio.gather(
        *(
            rabbitmq_client.subscribe(
                SchedulePipelineRabbitMessage.get_channel_name(),
                functools.partial(_handle_apply_distributed_schedule, app),
                exclusive_queue=False,
            )
            for _ in range(
                app_settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND.COMPUTATIONAL_BACKEND_SCHEDULING_CONCURRENCY
            )
        )
    )

    app.state.scheduler_worker = create_scheduler(app)


async def shutdown_worker(app: FastAPI) -> None:
    assert app.state.scheduler_worker  # nosec
    rabbitmq_client = get_rabbitmq_client(app)
    await asyncio.gather(
        *(
            rabbitmq_client.unsubscribe_consumer(*consumer)
            for consumer in app.state.scheduler_worker_consumers
        ),
        return_exceptions=False,
    )
