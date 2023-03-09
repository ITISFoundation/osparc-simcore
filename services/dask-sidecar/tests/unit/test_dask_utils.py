# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member


import asyncio
import concurrent.futures
import time
from typing import Any

import distributed
import pytest
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.events import TaskLogEvent
from dask_task_models_library.container_tasks.io import TaskCancelEventName
from simcore_service_dask_sidecar.boot_mode import BootMode
from simcore_service_dask_sidecar.dask_utils import (
    get_current_task_boot_mode,
    get_current_task_resources,
    is_current_task_aborted,
    monitor_task_abortion,
    publish_event,
)
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

DASK_TASK_STARTED_EVENT = "task_started"
DASK_TESTING_TIMEOUT_S = 25


async def test_publish_event(dask_client: distributed.Client):
    dask_pub = distributed.Pub("some_topic")
    dask_sub = distributed.Sub("some_topic")
    async for attempt in AsyncRetrying(
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(0.01),
        stop=stop_after_delay(60),
    ):
        with attempt:
            print(
                f"waiting for subscribers... attempt={attempt.retry_state.attempt_number}"
            )
            assert dask_pub.subscribers
            print("we do have subscribers!")

    event_to_publish = TaskLogEvent(job_id="some_fake_job_id", log="the log")
    publish_event(dask_pub=dask_pub, event=event_to_publish)
    # NOTE: this tests runs a sync dask client,
    # and the CI seems to have sometimes difficulties having this run in a reasonable time
    # hence the long time out
    message = dask_sub.get(timeout=DASK_TESTING_TIMEOUT_S)
    assert message is not None
    received_task_log_event = TaskLogEvent.parse_raw(message)  # type: ignore
    assert received_task_log_event == event_to_publish


def _wait_for_task_to_start():
    start_event = distributed.Event(DASK_TASK_STARTED_EVENT)
    start_event.wait(timeout=DASK_TESTING_TIMEOUT_S)


def _notify_task_is_started_and_ready():
    start_event = distributed.Event(DASK_TASK_STARTED_EVENT)
    start_event.set()


def _some_long_running_task() -> int:
    assert is_current_task_aborted() == False
    _notify_task_is_started_and_ready()

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
    _wait_for_task_to_start()
    future.cancel()
    assert future.cancelled()
    with pytest.raises(concurrent.futures.CancelledError):
        future.result(timeout=DASK_TESTING_TIMEOUT_S)


def test_task_is_aborted_using_event(dask_client: distributed.Client):
    job_id = "myfake_job_id"
    future = dask_client.submit(_some_long_running_task, key=job_id)
    _wait_for_task_to_start()

    dask_event = distributed.Event(TaskCancelEventName.format(job_id))
    dask_event.set()

    result = future.result(timeout=2)
    assert result == -1


def _some_long_running_task_with_monitoring() -> int:
    assert is_current_task_aborted() == False
    # we are started now
    start_event = distributed.Event(DASK_TASK_STARTED_EVENT)
    start_event.set()

    async def _long_running_task_async() -> int:
        log_publisher = distributed.Pub(TaskLogEvent.topic_name())
        _notify_task_is_started_and_ready()
        async with monitor_task_abortion(task_name=asyncio.current_task().get_name(), log_publisher=log_publisher):  # type: ignore
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


def test_monitor_task_abortion(dask_client: distributed.Client):
    job_id = "myfake_job_id"
    future = dask_client.submit(_some_long_running_task_with_monitoring, key=job_id)
    _wait_for_task_to_start()
    # trigger cancellation
    dask_event = distributed.Event(TaskCancelEventName.format(job_id))
    dask_event.set()
    with pytest.raises(TaskCancelledError):
        future.result(timeout=DASK_TESTING_TIMEOUT_S)


@pytest.mark.parametrize(
    "resources, expected_boot_mode",
    [
        ({"CPU": 2}, BootMode.CPU),
        ({"MPI": 1.0}, BootMode.MPI),
        ({"GPU": 5.0}, BootMode.GPU),
    ],
)
def test_task_boot_mode(
    dask_client: distributed.Client,
    resources: dict[str, Any],
    expected_boot_mode: BootMode,
):
    future = dask_client.submit(get_current_task_boot_mode, resources=resources)
    received_boot_mode = future.result(timeout=DASK_TESTING_TIMEOUT_S)
    assert received_boot_mode == expected_boot_mode


@pytest.mark.parametrize(
    "resources",
    [
        ({"CPU": 2}),
        ({"MPI": 1.0}),
        ({"GPU": 5.0}),
    ],
)
def test_task_resources(
    dask_client: distributed.Client,
    resources: dict[str, Any],
):
    future = dask_client.submit(get_current_task_resources, resources=resources)
    received_resources = future.result(timeout=DASK_TESTING_TIMEOUT_S)
    assert received_resources == resources
