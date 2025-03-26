import asyncio
import datetime
import logging
import time
from collections.abc import Callable, Iterable
from random import randint
from typing import Any

import pytest
from celery import Celery, Task
from celery.contrib.abortable import AbortableTask
from celery.contrib.testing.worker import TestWorkController, start_worker
from celery.signals import worker_init, worker_shutdown
from common_library.errors_classes import OsparcErrorMixin
from models_library.progress_bar import ProgressReport
from pydantic import TypeAdapter, ValidationError
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.logging_utils import config_all_loggers, log_context
from simcore_service_storage.core.settings import ApplicationSettings
from simcore_service_storage.modules.celery import get_event_loop
from simcore_service_storage.modules.celery._task import define_task
from simcore_service_storage.modules.celery.client import CeleryTaskQueueClient
from simcore_service_storage.modules.celery.models import (
    TaskContext,
    TaskError,
    TaskState,
)
from simcore_service_storage.modules.celery.signals import (
    on_worker_init,
    on_worker_shutdown,
)
from simcore_service_storage.modules.celery.utils import (
    get_celery_worker,
    get_fastapi_app,
)
from tenacity import Retrying, retry_if_exception_type, stop_after_delay, wait_fixed

_logger = logging.getLogger(__name__)

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def celery_conf() -> dict[str, Any]:
    return {
        "broker_url": "memory://",
        "result_backend": "cache+memory://",
        "result_expires": datetime.timedelta(days=7),
        "result_extended": True,
        "pool": "threads",
        "worker_send_task_events": True,
        "task_track_started": True,
        "task_send_sent_event": True,
        "broker_connection_retry_on_startup": True,
    }


@pytest.fixture
def celery_app(celery_conf: dict[str, Any]):
    return Celery(**celery_conf)


@pytest.fixture
def celery_client(
    app_environment: EnvVarsDict, celery_app: Celery
) -> CeleryTaskQueueClient:
    return CeleryTaskQueueClient(celery_app)


@pytest.fixture
def celery_worker_controller(
    app_environment: EnvVarsDict,
    app_settings: ApplicationSettings,
    register_celery_tasks: Callable[[Celery], None],
    celery_app: Celery,
) -> Iterable[TestWorkController]:
    # Signals must be explicitily connected
    logging.basicConfig(level=logging.WARNING)  # NOSONAR
    logging.root.setLevel(app_settings.log_level)
    config_all_loggers(
        log_format_local_dev_enabled=app_settings.STORAGE_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=app_settings.STORAGE_LOG_FILTER_MAPPING,
        tracing_settings=app_settings.STORAGE_TRACING,
    )
    worker_init.connect(on_worker_init)
    worker_shutdown.connect(on_worker_shutdown)

    register_celery_tasks(celery_app)

    with start_worker(
        celery_app,
        pool="threads",
        loglevel="info",
        perform_ping_check=False,
        worker_kwargs={"hostname": "celery@worker1"},
    ) as worker:
        worker_init.send(sender=worker)

        yield worker

        worker_shutdown.send(sender=worker)


async def _async_archive(
    celery_app: Celery, task_name: str, task_id: str, files: list[str]
) -> str:
    worker = get_celery_worker(celery_app)

    def sleep_for(seconds: float) -> None:
        time.sleep(seconds)

    for n, file in enumerate(files, start=1):
        with log_context(_logger, logging.INFO, msg=f"Processing file {file}"):
            worker.set_task_progress(
                task_name=task_name,
                task_id=task_id,
                report=ProgressReport(actual_value=n / len(files) * 10),
            )
            await asyncio.get_event_loop().run_in_executor(None, sleep_for, 1)

    return "archive.zip"


def sync_archive(task: Task, files: list[str]) -> str:
    assert task.name
    _logger.info("Calling async_archive")
    return asyncio.run_coroutine_threadsafe(
        _async_archive(task.app, task.name, task.request.id, files),
        get_event_loop(get_fastapi_app(task.app)),
    ).result()


class MyError(OsparcErrorMixin, Exception):
    msg_template = "Something strange happened: {msg}"


def failure_task(task: Task):
    assert task
    msg = "BOOM!"
    raise MyError(msg=msg)


def dreamer_task(task: AbortableTask) -> list[int]:
    numbers = []
    for _ in range(30):
        if task.is_aborted():
            _logger.warning("Alarm clock")
            return numbers
        numbers.append(randint(1, 90))  # noqa: S311
        time.sleep(0.1)
    return numbers


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    def _(celery_app: Celery) -> None:
        define_task(celery_app, sync_archive)
        define_task(celery_app, failure_task)
        define_task(celery_app, dreamer_task)

    return _


@pytest.mark.usefixtures("celery_worker")
async def test_submitting_task_calling_async_function_results_with_success_state(
    celery_client: CeleryTaskQueueClient,
):
    task_context = TaskContext(user_id=42)

    task_uuid = await celery_client.send_task(
        "sync_archive",
        task_context=task_context,
        files=[f"file{n}" for n in range(5)],
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            status = await celery_client.get_task_status(task_context, task_uuid)
            assert status.task_state == TaskState.SUCCESS

    assert (
        await celery_client.get_task_status(task_context, task_uuid)
    ).task_state == TaskState.SUCCESS
    assert (
        await celery_client.get_task_result(task_context, task_uuid)
    ) == "archive.zip"


@pytest.mark.usefixtures("celery_worker")
async def test_submitting_task_with_failure_results_with_error(
    celery_client: CeleryTaskQueueClient,
):
    task_context = TaskContext(user_id=42)

    task_uuid = await celery_client.send_task("failure_task", task_context=task_context)

    for attempt in Retrying(
        retry=retry_if_exception_type((AssertionError, ValidationError)),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            raw_result = await celery_client.get_task_result(task_context, task_uuid)
            result = TypeAdapter(TaskError).validate_python(raw_result)
            assert isinstance(result, TaskError)

    assert (
        await celery_client.get_task_status(task_context, task_uuid)
    ).task_state == TaskState.ERROR
    raw_result = await celery_client.get_task_result(task_context, task_uuid)
    result = TypeAdapter(TaskError).validate_python(raw_result)
    assert f"{result.exc_msg}" == "Something strange happened: BOOM!"


@pytest.mark.usefixtures("celery_worker")
async def test_aborting_task_results_with_aborted_state(
    celery_client: CeleryTaskQueueClient,
):
    task_context = TaskContext(user_id=42)

    task_uuid = await celery_client.send_task(
        "dreamer_task",
        task_context=task_context,
    )

    await celery_client.abort_task(task_context, task_uuid)

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            progress = await celery_client.get_task_status(task_context, task_uuid)
            assert progress.task_state == TaskState.ABORTED

    assert (
        await celery_client.get_task_status(task_context, task_uuid)
    ).task_state == TaskState.ABORTED


@pytest.mark.usefixtures("celery_worker")
async def test_listing_task_uuids_contains_submitted_task(
    celery_client: CeleryTaskQueueClient,
):
    task_context = TaskContext(user_id=42)

    task_uuid = await celery_client.send_task(
        "dreamer_task",
        task_context=task_context,
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(0.1),
        stop=stop_after_delay(10),
    ):
        with attempt:
            assert task_uuid in await celery_client.get_task_uuids(task_context)

    assert task_uuid in await celery_client.get_task_uuids(task_context)
