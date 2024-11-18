import functools
import logging
from collections.abc import Callable, Coroutine
from typing import Any, cast

from fastapi import FastAPI
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.logging_utils import log_context
from simcore_service_director_v2.modules.comp_scheduler._base_scheduler import (
    BaseCompScheduler,
)

from ..rabbitmq import get_rabbitmq_client
from ._distributed_scheduler import (
    SCHEDULER_INTERVAL,
    run_new_pipeline,
    schedule_pipelines,
    stop_pipeline,
)
from ._models import SchedulePipelineRabbitMessage
from ._scheduler_factory import create_scheduler

_logger = logging.getLogger(__name__)


def _empty_wake_up_callack() -> None:
    return


async def _handle_distributed_pipeline(app: FastAPI, data: bytes) -> bool:
    to_schedule_pipeline = SchedulePipelineRabbitMessage.parse_raw(data)
    await _get_scheduler_worker(app)._schedule_pipeline(
        user_id=to_schedule_pipeline.user_id,
        project_id=to_schedule_pipeline.project_id,
        iteration=to_schedule_pipeline.iteration,
        wake_up_callback=_empty_wake_up_callack,
    )
    return True


def on_app_startup(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def start_scheduler() -> None:
        with log_context(
            _logger, level=logging.INFO, msg="starting computational scheduler"
        ):
            rabbitmq_client = get_rabbitmq_client(app)
            await rabbitmq_client.subscribe(
                SchedulePipelineRabbitMessage.get_channel_name(),
                functools.partial(_handle_distributed_pipeline, app),
                exclusive_queue=False,
            )

            app.state.scheduler_worker = create_scheduler(app)

            app.state.scheduler_manager = start_periodic_task(
                schedule_pipelines,
                interval=SCHEDULER_INTERVAL,
                task_name="computational-distributed-scheduler",
            )

    return start_scheduler


def on_app_shutdown(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def stop_scheduler() -> None:
        with log_context(
            _logger, level=logging.INFO, msg="stopping computational scheduler"
        ):
            await stop_periodic_task(app.state.scheduler_manager)

            # TODO: we might want to stop anything running in the worker too

    return stop_scheduler


def _get_scheduler_worker(app: FastAPI) -> BaseCompScheduler:
    return cast(BaseCompScheduler, app.state.scheduler_worker)


def setup(app: FastAPI):
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))


__all__: tuple[str, ...] = (
    "setup",
    "run_new_pipeline",
    "stop_pipeline",
)
