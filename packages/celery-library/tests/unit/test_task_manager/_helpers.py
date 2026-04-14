"""Shared task definitions and helper functions for test_task_manager tests."""

# pylint: disable=unused-argument

import asyncio
import logging
import time
from random import randint

from celery import Celery, Task  # pylint: disable=no-name-in-module
from celery_library.worker.app_server import get_app_server
from common_library.errors_classes import OsparcErrorMixin
from models_library.celery import (
    TASK_DONE_STATES,
    OwnerMetadata,
    TaskKey,
    TaskState,
    TaskStatus,
    TaskStreamItem,
    TaskUUID,
)
from models_library.progress_bar import ProgressReport
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_context
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

_logger = logging.getLogger(__name__)

_TENACITY_RETRY_PARAMS: dict = {
    "reraise": True,
    "retry": retry_if_exception_type(AssertionError),
    "stop": stop_after_delay(30),
    "wait": wait_fixed(0.1),
}


async def fake_file_processor_impl(celery_app: Celery, task_name: str, task_key: str, files: list[str]) -> str:
    def sleep_for(seconds: float) -> None:
        time.sleep(seconds)

    for n, file in enumerate(files, start=1):
        with log_context(_logger, logging.INFO, msg=f"Processing file {file}"):
            await get_app_server(celery_app).task_manager.set_task_progress(
                task_key=task_key,
                report=ProgressReport(actual_value=n / len(files)),
            )
            await asyncio.get_event_loop().run_in_executor(None, sleep_for, 1)

    return "archive.zip"


def fake_file_processor(task: Task, task_key: TaskKey, files: list[str]) -> str:
    assert task_key
    assert task.name
    _logger.info("Calling fake_file_processor_impl")
    return asyncio.run_coroutine_threadsafe(
        fake_file_processor_impl(task.app, task.name, task.request.id, files),
        get_app_server(task.app).event_loop,
    ).result()


class MyError(OsparcErrorMixin, Exception):
    msg_template = "Something strange happened: {msg}"


def failure_task(task: Task, task_key: TaskKey) -> None:
    assert task_key
    assert task
    msg = "BOOM!"
    raise MyError(msg=msg)


async def dreamer_task(task: Task, task_key: TaskKey) -> list[int]:
    numbers = []
    for _ in range(30):
        numbers.append(randint(1, 90))  # noqa: S311
        await asyncio.sleep(0.5)
    return numbers


def streaming_results_task(task: Task, task_key: TaskKey, num_results: int = 5) -> str:
    assert task_key
    assert task.name

    async def _stream_results(sleep_interval: float) -> None:
        app_server = get_app_server(task.app)
        for i in range(num_results):
            result_data = f"result-{i}"
            result_item = TaskStreamItem(data=result_data)
            await app_server.task_manager.push_task_stream_items(
                task_key,
                result_item,
            )
            _logger.info("Pushed result %d: %s", i, result_data)
            await asyncio.sleep(sleep_interval)

        # Mark the stream as done
        await app_server.task_manager.set_task_stream_done(task_key)

    # Run the streaming in the event loop
    asyncio.run_coroutine_threadsafe(_stream_results(0.5), get_app_server(task.app).event_loop).result()

    return f"completed-{num_results}-results"


async def wait_for_task_success(
    task_manager: TaskManager,
    owner_metadata: OwnerMetadata,
    task_uuid: TaskUUID,
) -> None:
    """Wait for a task to reach SUCCESS state."""
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            status = await task_manager.get_status(owner_metadata, task_uuid)
            assert isinstance(status, TaskStatus)
            assert status.task_state == TaskState.SUCCESS


async def wait_for_task_done(
    task_manager: TaskManager,
    owner_metadata: OwnerMetadata,
    task_uuid: TaskUUID,
) -> None:
    """Wait for a task to reach any DONE state."""
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            status = await task_manager.get_status(owner_metadata, task_uuid)
            assert isinstance(status, TaskStatus)
            assert status.task_state in TASK_DONE_STATES
