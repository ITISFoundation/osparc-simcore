# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member


import asyncio
import concurrent.futures
import time
from typing import Any, Dict

import distributed
import pytest
from dask_task_models_library.container_tasks.events import (
    TaskCancelEvent,
    TaskLogEvent,
)
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
    message = dask_sub.get(timeout=1)
    assert message is not None
    received_task_log_event = TaskLogEvent.parse_raw(message)  # type: ignore
    assert received_task_log_event == event_to_publish


def _some_long_running_task() -> int:
    dask_sub = distributed.Sub(TaskCancelEvent.topic_name())
    assert is_current_task_aborted(dask_sub) == False
    for i in range(300):
        print("running iteration", i)
        time.sleep(0.1)
        if is_current_task_aborted(dask_sub):
            print("task is aborted")
            return -1
    assert is_current_task_aborted(dask_sub)
    return 12


def test_task_is_aborted(dask_client: distributed.Client):
    # NOTE: this works because the cluster is in the same machine
    future = dask_client.submit(_some_long_running_task)
    time.sleep(1)
    future.cancel()
    time.sleep(1)
    assert future.cancelled()
    with pytest.raises(concurrent.futures.CancelledError):
        future.result(timeout=5)


def test_task_is_aborted_using_pub(dask_client: distributed.Client):
    job_id = "myfake_job_id"
    future = dask_client.submit(_some_long_running_task, key=job_id)
    time.sleep(1)
    dask_pub = distributed.Pub(TaskCancelEvent.topic_name())
    dask_pub.put(TaskCancelEvent(job_id=job_id).json())

    result = future.result(timeout=2)
    assert result == -1


def _some_long_running_task_with_monitoring() -> int:
    async def _long_running_task_async() -> int:
        async with monitor_task_abortion(task_name=asyncio.current_task().get_name()):  # type: ignore
            for i in range(300):
                print("running iteration", i)
                await asyncio.sleep(0.5)
            return 12

    return asyncio.get_event_loop().run_until_complete(_long_running_task_async())


def test_monitor_task_abortion(dask_client: distributed.Client):
    job_id = "myfake_job_id"
    future = dask_client.submit(_some_long_running_task_with_monitoring, key=job_id)
    time.sleep(1)
    # trigger cancellation
    dask_pub = distributed.Pub(TaskCancelEvent.topic_name())
    dask_pub.put(TaskCancelEvent(job_id=job_id).json())
    result = future.result(timeout=10)
    assert result is None


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
    resources: Dict[str, Any],
    expected_boot_mode: BootMode,
):
    future = dask_client.submit(get_current_task_boot_mode, resources=resources)
    received_boot_mode = future.result(timeout=1)
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
    resources: Dict[str, Any],
):
    future = dask_client.submit(get_current_task_resources, resources=resources)
    received_resources = future.result(timeout=1)
    assert received_resources == resources
