# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member


import asyncio
import concurrent.futures
import logging
import time
from typing import Any
from unittest import mock

import distributed
import pytest
from common_library.async_tools import maybe_await
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.events import TaskProgressEvent
from dask_task_models_library.container_tasks.io import TaskCancelEventName
from dask_task_models_library.container_tasks.protocol import TaskOwner
from pytest_simcore.helpers.logging_tools import log_context
from simcore_service_dask_sidecar.utils.dask import (
    _DEFAULT_MAX_RESOURCES,
    TaskPublisher,
    get_current_task_resources,
    is_current_task_aborted,
    monitor_task_abortion,
    publish_event,
)
from tenacity import Retrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

DASK_TASK_STARTED_EVENT = "task_started"
DASK_TESTING_TIMEOUT_S = 25

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture(params=["sync-dask-client", "async-dask-client"])
def dask_client_multi(
    request: pytest.FixtureRequest,
    dask_client: distributed.Client,
    async_dask_client: distributed.Client,
) -> distributed.Client:
    if request.param == "sync-dask-client":
        return dask_client
    return async_dask_client


@pytest.mark.parametrize(
    "handler", [mock.Mock(), mock.AsyncMock()], ids=["sync-handler", "async-handler"]
)
async def test_publish_event(
    dask_client_multi: distributed.Client,
    job_id: str,
    task_owner: TaskOwner,
    handler: mock.Mock | mock.AsyncMock,
):
    event_to_publish = TaskProgressEvent(
        job_id=job_id,
        msg="the log",
        progress=1,
        task_owner=task_owner,
    )

    # NOTE: only 1 handler per topic is allowed at a time
    dask_client_multi.subscribe_topic(TaskProgressEvent.topic_name(), handler)

    def _worker_task() -> int:
        with log_context(logging.INFO, "_worker_task"):

            async def _() -> int:
                with log_context(logging.INFO, "_worker_task_async"):
                    await publish_event(event_to_publish)
                    return 2

            return asyncio.run(_())

    future = dask_client_multi.submit(_worker_task)
    assert await maybe_await(future.result(timeout=DASK_TESTING_TIMEOUT_S)) == 2

    for attempt in Retrying(
        wait=wait_fixed(0.2),
        stop=stop_after_delay(15),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            events = await maybe_await(
                dask_client_multi.get_events(TaskProgressEvent.topic_name())
            )
            assert events is not None, "No events received"
            assert isinstance(events, tuple)

            handler.assert_called_with(events[-1])

    assert isinstance(events, tuple)
    assert len(events) == 1
    assert isinstance(events[0], tuple)
    received_task_log_event = TaskProgressEvent.model_validate_json(events[0][1])
    assert received_task_log_event == event_to_publish


def _wait_for_task_to_start(dask_client: distributed.Client) -> None:
    start_event = distributed.Event(DASK_TASK_STARTED_EVENT, dask_client)
    start_event.wait(timeout=DASK_TESTING_TIMEOUT_S)


def _notify_task_is_started_and_ready(dask_client: distributed.Client) -> None:
    start_event = distributed.Event(DASK_TASK_STARTED_EVENT, dask_client)
    start_event.set()


def _some_long_running_task() -> int:
    assert is_current_task_aborted() is False
    dask_client = distributed.get_worker().client
    _notify_task_is_started_and_ready(dask_client)

    for i in range(300):
        print("running iteration", i)
        time.sleep(0.1)
        if is_current_task_aborted():
            print("task is aborted")
            return -1
    assert is_current_task_aborted()
    return 12


def test_task_is_aborted(dask_client: distributed.Client):
    """Tests aborting a task without using an event. In theory once
    the future is cancelled, the dask worker shall 'forget' the task. Sadly this does
    not work in distributed mode where an Event is necessary."""
    # NOTE: this works because the cluster is in the same machine
    future = dask_client.submit(_some_long_running_task)
    _wait_for_task_to_start(dask_client)
    future.cancel()
    assert future.cancelled()
    with pytest.raises(concurrent.futures.CancelledError):
        future.result(timeout=DASK_TESTING_TIMEOUT_S)


def test_task_is_aborted_using_event(dask_client: distributed.Client):
    job_id = "myfake_job_id"
    future = dask_client.submit(_some_long_running_task, key=job_id)
    _wait_for_task_to_start(dask_client)

    dask_event = distributed.Event(TaskCancelEventName.format(job_id))
    dask_event.set()

    result = future.result(timeout=2)
    assert result == -1


def _some_long_running_task_with_monitoring(task_owner: TaskOwner) -> int:
    assert is_current_task_aborted() is False
    # we are started now
    start_event = distributed.Event(DASK_TASK_STARTED_EVENT)
    start_event.set()

    async def _long_running_task_async() -> int:
        task_publishers = TaskPublisher(task_owner=task_owner)
        worker = distributed.get_worker()
        _notify_task_is_started_and_ready(worker.client)
        current_task = asyncio.current_task()
        assert current_task
        async with monitor_task_abortion(
            task_name=current_task.get_name(), task_publishers=task_publishers
        ):
            for i in range(300):
                print("running iteration", i)
                await asyncio.sleep(0.5)
            return 12

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # NOTE: this happens in testing when the dask cluster runs INProcess
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return asyncio.get_event_loop().run_until_complete(_long_running_task_async())


def test_monitor_task_abortion(
    dask_client: distributed.Client, job_id: str, task_owner: TaskOwner
):
    future = dask_client.submit(
        _some_long_running_task_with_monitoring, task_owner=task_owner, key=job_id
    )
    _wait_for_task_to_start(dask_client)
    # trigger cancellation
    dask_event = distributed.Event(TaskCancelEventName.format(job_id))
    dask_event.set()
    with pytest.raises(TaskCancelledError):
        future.result(timeout=DASK_TESTING_TIMEOUT_S)


@pytest.mark.parametrize(
    "resources",
    [
        ({"CPU": 2}),
        ({"GPU": 5.0}),
    ],
)
def test_task_resources(
    dask_client: distributed.Client,
    resources: dict[str, Any],
):
    future = dask_client.submit(get_current_task_resources, resources=resources)
    received_resources = future.result(timeout=DASK_TESTING_TIMEOUT_S)
    current_resources = _DEFAULT_MAX_RESOURCES
    current_resources.update(resources)
    assert received_resources == current_resources
