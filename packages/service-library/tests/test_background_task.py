# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import datetime
from typing import AsyncIterator, Awaitable, Callable
from unittest import mock

import pytest
from faker import Faker
from pytest_mock.plugin import MockerFixture
from servicelib.background_task import start_periodic_task, stop_periodic_task

_FAST_POLL_INTERVAL = 1


@pytest.fixture
def mock_background_task(mocker: MockerFixture) -> mock.AsyncMock:
    mocked_task = mocker.AsyncMock(return_value=None)
    return mocked_task


@pytest.fixture
def task_interval() -> datetime.timedelta:
    return datetime.timedelta(seconds=_FAST_POLL_INTERVAL)


@pytest.fixture
async def create_background_task(
    faker: Faker,
) -> AsyncIterator[Callable[[datetime.timedelta, Callable], Awaitable[asyncio.Task]]]:
    created_tasks = []

    async def _creator(
        interval: datetime.timedelta, task: Callable[..., Awaitable]
    ) -> asyncio.Task:
        background_task = await start_periodic_task(
            task,
            interval=interval,
            task_name=faker.pystr(),
        )
        assert background_task
        created_tasks.append(background_task)
        return background_task

    yield _creator
    # cleanup
    await asyncio.gather(*(stop_periodic_task(t) for t in created_tasks))


async def test_background_task_created_and_deleted(
    mock_background_task: mock.AsyncMock,
    task_interval: datetime.timedelta,
    create_background_task: Callable[
        [datetime.timedelta, Callable], Awaitable[asyncio.Task]
    ],
):
    task = await create_background_task(
        task_interval,
        mock_background_task,
    )
    await asyncio.sleep(5 * task_interval.total_seconds())
    mock_background_task.assert_called()


async def test_dynamic_scaling_task_raises_restarts(
    mock_background_task: mock.AsyncMock,
    task_interval: datetime.timedelta,
    create_background_task: Callable[
        [datetime.timedelta, Callable], Awaitable[asyncio.Task]
    ],
):
    mock_background_task.side_effect = RuntimeError("pytest faked runtime error")
    task = await create_background_task(
        task_interval,
        mock_background_task,
    )
    await asyncio.sleep(5 * task_interval.total_seconds())
    mock_background_task.assert_called()
    assert mock_background_task.call_count > 1


async def test_dynamic_scaling_task_correctly_cancels(
    mock_background_task: mock.AsyncMock,
    task_interval: datetime.timedelta,
    create_background_task: Callable[
        [datetime.timedelta, Callable], Awaitable[asyncio.Task]
    ],
):
    mock_background_task.side_effect = asyncio.CancelledError
    task = await create_background_task(
        task_interval,
        mock_background_task,
    )
    await asyncio.sleep(5 * task_interval.total_seconds())
    # the task will be called once, and then stop
    mock_background_task.assert_called_once()
