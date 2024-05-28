# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from faker import Faker
from servicelib.deferred_tasks._base_deferred_handler import DeferredContext
from servicelib.deferred_tasks._deferred_manager import (
    _DEFAULT_DEFERRED_MANAGER_WORKER_SLOTS,
)
from servicelib.deferred_tasks._models import (
    TaskResultCancelledError,
    TaskResultError,
    TaskResultSuccess,
    TaskUID,
)
from servicelib.deferred_tasks._worker_tracker import WorkerTracker


async def _worker(tracker: WorkerTracker) -> None:
    async with tracker:
        await asyncio.sleep(1)


async def test_worker_tracker_full():
    tracker_size = 2
    tracker = WorkerTracker(tracker_size)

    tasks = [asyncio.create_task(_worker(tracker)) for _ in range(tracker_size)]
    # context switch to allow tasks to be picked up
    await asyncio.sleep(0.01)

    assert tracker.has_free_slots() is False
    await asyncio.gather(*tasks)
    assert tracker.has_free_slots() is True


async def test_worker_tracker_filling_up_gradually():
    tracker_size = 10
    tracker = WorkerTracker(tracker_size)

    tasks = []
    for _ in range(tracker_size):
        assert tracker.has_free_slots() is True

        tasks.append(asyncio.create_task(_worker(tracker)))
        # context switch to allow task to be picked up
        await asyncio.sleep(0.01)

    assert tracker.has_free_slots() is False
    await asyncio.gather(*tasks)
    assert tracker.has_free_slots() is True


@pytest.fixture
def worker_tracker() -> WorkerTracker:
    return WorkerTracker(_DEFAULT_DEFERRED_MANAGER_WORKER_SLOTS)


@pytest.fixture
def task_uid(faker: Faker) -> TaskUID:
    return faker.uuid4()


def _get_mock_deferred_handler(handler: Callable[..., Awaitable[Any]]) -> AsyncMock:
    async_mock = AsyncMock()
    async_mock.run = handler
    return async_mock


async def __h_return_constant_integer(full_start_context) -> int:
    _ = full_start_context
    return 42


async def __h_sum_numbers(deferred_context: DeferredContext) -> float:
    return deferred_context["first"] + deferred_context["second"]


async def __h_stringify(deferred_context: DeferredContext) -> str:

    return f"{deferred_context['name']} is {deferred_context['age']} years old"


async def __h_do_nothing(deferred_context: DeferredContext) -> None:
    _ = deferred_context


@pytest.mark.parametrize(
    "handler, context, expected_result",
    [
        (__h_return_constant_integer, {}, 42),
        (__h_sum_numbers, {"first": 4, "second": 0.14}, 4.14),
        (__h_stringify, {"name": "John", "age": 56}, "John is 56 years old"),
        (__h_do_nothing, {}, None),
        (__h_do_nothing, {"first": "arg", "second": "argument"}, None),
    ],
)
async def test_returns_task_result_success(
    worker_tracker: WorkerTracker,
    task_uid: TaskUID,
    handler: Callable[..., Awaitable[Any]],
    context: DeferredContext,
    expected_result: Any,
):

    deferred_handler = _get_mock_deferred_handler(handler)
    result = await worker_tracker.handle_run(
        deferred_handler,  # type: ignore
        task_uid=task_uid,
        deferred_context=context,
        timeout=timedelta(seconds=0.1),
    )
    assert isinstance(result, TaskResultSuccess)
    assert result.value == expected_result
    assert len(worker_tracker._tasks) == 0  # noqa: SLF001


async def test_returns_task_result_error(
    worker_tracker: WorkerTracker,
    task_uid: TaskUID,
):
    async def _handler(deferred_context: DeferredContext) -> None:
        msg = "raising an error as expected"
        raise RuntimeError(msg)

    deferred_handler = _get_mock_deferred_handler(_handler)
    result = await worker_tracker.handle_run(
        deferred_handler,  # type: ignore
        task_uid=task_uid,
        deferred_context={},
        timeout=timedelta(seconds=0.1),
    )
    assert isinstance(result, TaskResultError)
    assert "raising an error as expected" in result.format_error()
    assert len(worker_tracker._tasks) == 0  # noqa: SLF001


async def test_returns_task_result_cancelled_error(
    worker_tracker: WorkerTracker,
    task_uid: TaskUID,
):
    async def _handler(deferred_context: DeferredContext) -> None:
        await asyncio.sleep(1e6)

    deferred_handler = _get_mock_deferred_handler(_handler)

    def _start_in_task() -> asyncio.Task:
        return asyncio.create_task(
            worker_tracker.handle_run(
                deferred_handler,  # type: ignore
                task_uid=task_uid,
                deferred_context={},
                timeout=timedelta(seconds=100),
            )
        )

    task = _start_in_task()
    # context switch for task to start
    await asyncio.sleep(0)
    assert worker_tracker.cancel_run(task_uid) is True

    assert len(worker_tracker._tasks) == 1  # noqa: SLF001
    result = await task
    assert len(worker_tracker._tasks) == 0  # noqa: SLF001
    assert isinstance(result, TaskResultCancelledError)

    assert worker_tracker.cancel_run("missing_task_uid") is False
