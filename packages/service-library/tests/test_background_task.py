# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import datetime
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Final
from unittest import mock

import pytest
from faker import Faker
from pytest_mock.plugin import MockerFixture
from servicelib.background_task import (
    periodic_task,
    start_periodic_task,
    stop_periodic_task,
)

_FAST_POLL_INTERVAL: Final[int] = 1
_VERY_SLOW_POLL_INTERVAL: Final[int] = 100


@pytest.fixture
def mock_background_task(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.AsyncMock(return_value=None)


@pytest.fixture
def task_interval() -> datetime.timedelta:
    return datetime.timedelta(seconds=_FAST_POLL_INTERVAL)


@pytest.fixture
def very_long_task_interval() -> datetime.timedelta:
    return datetime.timedelta(seconds=_VERY_SLOW_POLL_INTERVAL)


@pytest.fixture(params=[None, 1], ids=lambda x: f"stop-timeout={x}")
def stop_task_timeout(request: pytest.FixtureRequest) -> float | None:
    return request.param


@pytest.fixture
async def create_background_task(
    faker: Faker, stop_task_timeout: float | None
) -> AsyncIterator[
    Callable[
        [datetime.timedelta, Callable, asyncio.Event | None], Awaitable[asyncio.Task]
    ]
]:
    created_tasks = []

    async def _creator(
        interval: datetime.timedelta,
        task: Callable[..., Awaitable],
        early_wake_up_event: asyncio.Event | None,
    ) -> asyncio.Task:
        background_task = start_periodic_task(
            task,
            interval=interval,
            task_name=faker.pystr(),
            early_wake_up_event=early_wake_up_event,
        )
        assert background_task
        created_tasks.append(background_task)
        return background_task

    yield _creator
    # cleanup
    await asyncio.gather(
        *(stop_periodic_task(t, timeout=stop_task_timeout) for t in created_tasks)
    )


@pytest.mark.parametrize(
    "wake_up_event", [None, asyncio.Event], ids=lambda x: f"wake-up-event: {x}"
)
async def test_background_task_created_and_deleted(
    mock_background_task: mock.AsyncMock,
    task_interval: datetime.timedelta,
    create_background_task: Callable[
        [datetime.timedelta, Callable, asyncio.Event | None], Awaitable[asyncio.Task]
    ],
    wake_up_event: Callable | None,
):
    event = wake_up_event() if wake_up_event else None
    _task = await create_background_task(
        task_interval,
        mock_background_task,
        event,
    )
    await asyncio.sleep(5 * task_interval.total_seconds())
    mock_background_task.assert_called()
    assert mock_background_task.call_count > 2


async def test_background_task_wakes_up_early(
    mock_background_task: mock.AsyncMock,
    very_long_task_interval: datetime.timedelta,
    create_background_task: Callable[
        [datetime.timedelta, Callable, asyncio.Event | None], Awaitable[asyncio.Task]
    ],
):
    wake_up_event = asyncio.Event()
    _task = await create_background_task(
        very_long_task_interval,
        mock_background_task,
        wake_up_event,
    )
    await asyncio.sleep(5 * _FAST_POLL_INTERVAL)
    # now the task should have run only once
    mock_background_task.assert_called_once()
    await asyncio.sleep(5 * _FAST_POLL_INTERVAL)
    mock_background_task.assert_called_once()
    # this should wake up the task
    wake_up_event.set()
    await asyncio.sleep(5 * _FAST_POLL_INTERVAL)
    mock_background_task.assert_called()
    assert mock_background_task.call_count == 2
    # no change this now waits again a very long time
    await asyncio.sleep(5 * _FAST_POLL_INTERVAL)
    mock_background_task.assert_called()
    assert mock_background_task.call_count == 2


async def test_background_task_raises_restarts(
    mock_background_task: mock.AsyncMock,
    task_interval: datetime.timedelta,
    create_background_task: Callable[
        [datetime.timedelta, Callable, asyncio.Event | None], Awaitable[asyncio.Task]
    ],
):
    mock_background_task.side_effect = RuntimeError("pytest faked runtime error")
    _task = await create_background_task(
        task_interval,
        mock_background_task,
        None,
    )
    await asyncio.sleep(5 * task_interval.total_seconds())
    mock_background_task.assert_called()
    assert mock_background_task.call_count > 1


async def test_background_task_correctly_cancels(
    mock_background_task: mock.AsyncMock,
    task_interval: datetime.timedelta,
    create_background_task: Callable[
        [datetime.timedelta, Callable, asyncio.Event | None], Awaitable[asyncio.Task]
    ],
):
    mock_background_task.side_effect = asyncio.CancelledError
    _task = await create_background_task(
        task_interval,
        mock_background_task,
        None,
    )
    await asyncio.sleep(5 * task_interval.total_seconds())
    # the task will be called once, and then stop
    mock_background_task.assert_called_once()


async def test_periodic_task_context_manager(
    mock_background_task: mock.AsyncMock,
    task_interval: datetime.timedelta,
    faker: Faker,
):
    task_name = faker.pystr()
    async with periodic_task(
        mock_background_task, interval=task_interval, task_name=task_name
    ) as asyncio_task:
        assert asyncio_task.get_name() == task_name
        assert asyncio_task.cancelled() is False
        await asyncio.sleep(5 * task_interval.total_seconds())
        assert asyncio_task.cancelled() is False
        assert asyncio_task.done() is False
    assert asyncio_task.cancelled() is True
