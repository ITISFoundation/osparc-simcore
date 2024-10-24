# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member


import asyncio
import concurrent.futures
import logging
import time
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any

import distributed
import pytest
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.events import TaskLogEvent
from dask_task_models_library.container_tasks.io import TaskCancelEventName
from dask_task_models_library.container_tasks.protocol import TaskOwner
from simcore_service_dask_sidecar.dask_utils import (
    _DEFAULT_MAX_RESOURCES,
    TaskPublisher,
    get_current_task_resources,
    is_current_task_aborted,
    monitor_task_abortion,
    publish_event,
)
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

DASK_TASK_STARTED_EVENT = "task_started"
DASK_TESTING_TIMEOUT_S = 25


def test_publish_event(
    dask_client: distributed.Client, job_id: str, task_owner: TaskOwner
):
    dask_pub = distributed.Pub("some_topic", client=dask_client)
    dask_sub = distributed.Sub("some_topic", client=dask_client)
    event_to_publish = TaskLogEvent(
        job_id=job_id,
        log="the log",
        log_level=logging.INFO,
        task_owner=task_owner,
    )
    publish_event(dask_pub=dask_pub, event=event_to_publish)

    # NOTE: this tests runs a sync dask client,
    # and the CI seems to have sometimes difficulties having this run in a reasonable time
    # hence the long time out
    message = dask_sub.get(timeout=DASK_TESTING_TIMEOUT_S)
    assert message is not None
    assert isinstance(message, str)
    received_task_log_event = TaskLogEvent.model_validate_json(message)
    assert received_task_log_event == event_to_publish


async def test_publish_event_async(
    async_dask_client: distributed.Client, job_id: str, task_owner: TaskOwner
):
    dask_pub = distributed.Pub("some_topic", client=async_dask_client)
    dask_sub = distributed.Sub("some_topic", client=async_dask_client)
    event_to_publish = TaskLogEvent(
        job_id=job_id, log="the log", log_level=logging.INFO, task_owner=task_owner
    )
    publish_event(dask_pub=dask_pub, event=event_to_publish)

    # NOTE: this tests runs a sync dask client,
    # and the CI seems to have sometimes difficulties having this run in a reasonable time
    # hence the long time out
    message = dask_sub.get(timeout=DASK_TESTING_TIMEOUT_S)
    assert isinstance(message, Coroutine)
    message = await message
    assert message is not None
    received_task_log_event = TaskLogEvent.model_validate_json(message)
    assert received_task_log_event == event_to_publish


@pytest.fixture
async def asyncio_task() -> AsyncIterator[Callable[[Coroutine], asyncio.Task]]:
    created_tasks = []

    def _creator(coro: Coroutine) -> asyncio.Task:
        task = asyncio.create_task(coro, name="pytest_asyncio_task")
        created_tasks.append(task)
        return task

    yield _creator
    for task in created_tasks:
        task.cancel()

    await asyncio.gather(*created_tasks, return_exceptions=True)


async def test_publish_event_async_using_task(
    async_dask_client: distributed.Client,
    asyncio_task: Callable[[Coroutine], asyncio.Task],
    job_id: str,
    task_owner: TaskOwner,
):
    dask_pub = distributed.Pub("some_topic", client=async_dask_client)
    dask_sub = distributed.Sub("some_topic", client=async_dask_client)
    NUMBER_OF_MESSAGES = 1000
    received_messages = []

    async def _dask_sub_consumer_task(sub: distributed.Sub) -> None:
        print("--> starting consumer task")
        async for dask_event in sub:
            print(f"received {dask_event}")
            received_messages.append(dask_event)
        print("<-- finished consumer task")

    consumer_task = asyncio_task(_dask_sub_consumer_task(dask_sub))
    assert consumer_task

    async def _dask_publisher_task(pub: distributed.Pub) -> None:
        print("--> starting publisher task")
        for n in range(NUMBER_OF_MESSAGES):
            event_to_publish = TaskLogEvent(
                job_id=job_id,
                log=f"the log {n}",
                log_level=logging.INFO,
                task_owner=task_owner,
            )
            publish_event(dask_pub=pub, event=event_to_publish)
        print("<-- finished publisher task")

    publisher_task = asyncio_task(_dask_publisher_task(dask_pub))
    assert publisher_task

    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(AssertionError),
        stop=stop_after_delay(DASK_TESTING_TIMEOUT_S),
        wait=wait_fixed(0.01),
        reraise=True,
    ):
        with attempt:
            print(
                f"checking number of received messages...currently {len(received_messages)}"
            )
            assert len(received_messages) == NUMBER_OF_MESSAGES
            print("all expected messages received")


def _wait_for_task_to_start() -> None:
    start_event = distributed.Event(DASK_TASK_STARTED_EVENT)
    start_event.wait(timeout=DASK_TESTING_TIMEOUT_S)


def _notify_task_is_started_and_ready() -> None:
    start_event = distributed.Event(DASK_TASK_STARTED_EVENT)
    start_event.set()


def _some_long_running_task() -> int:
    assert is_current_task_aborted() is False
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


def _some_long_running_task_with_monitoring(task_owner: TaskOwner) -> int:
    assert is_current_task_aborted() is False
    # we are started now
    start_event = distributed.Event(DASK_TASK_STARTED_EVENT)
    start_event.set()

    async def _long_running_task_async() -> int:
        task_publishers = TaskPublisher(task_owner=task_owner)
        _notify_task_is_started_and_ready()
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
    _wait_for_task_to_start()
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
