# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
from collections.abc import AsyncIterator, Awaitable, Coroutine, Iterator
from copy import copy, deepcopy
from typing import NoReturn
from unittest import mock

import pytest
from faker import Faker
from pytest_mock import MockerFixture
from servicelib.utils import (
    ensure_ends_with,
    fire_and_forget_task,
    limited_as_completed,
    limited_gather,
    logged_gather,
)


async def _value_error(uid: int, *, delay: int = 1) -> NoReturn:
    await _succeed(uid, delay=delay)
    msg = f"task#{uid}"
    raise ValueError(msg)


async def _runtime_error(uid: int, *, delay: int = 1) -> NoReturn:
    await _succeed(uid, delay=delay)
    msg = f"task#{uid}"
    raise RuntimeError(msg)


async def _succeed(uid: int, *, delay: int = 1) -> int:
    print(f"task#{uid} begin")
    await asyncio.sleep(delay)
    print(f"task#{uid} end")
    return uid


@pytest.fixture
def coros() -> list[Coroutine]:
    return [
        _succeed(0),
        _value_error(1, delay=4),
        _succeed(2),
        _runtime_error(3, delay=0),
        _value_error(4, delay=2),
        _succeed(5),
    ]


@pytest.fixture
def mock_logger(mocker: MockerFixture) -> Iterator[mock.Mock]:
    mock_logger = mocker.Mock()

    yield mock_logger

    assert mock_logger.mock_calls
    mock_logger.warning.assert_called()
    assert (
        len(mock_logger.warning.mock_calls) == 3
    ), "Expected all 3 errors ALWAYS logged as warnings"


async def test_logged_gather(
    coros: list[Coroutine],
    mock_logger: mock.Mock,
):
    with pytest.raises(ValueError) as excinfo:  # noqa: PT011
        await logged_gather(*coros, reraise=True, log=mock_logger)

    # NOTE: #4 fails first, the one raised in #1
    assert "task#1" in str(excinfo.value)

    # NOTE: only first error in the list is raised, since it is not RuntimeError, that task
    assert isinstance(excinfo.value, ValueError)

    for task in asyncio.all_tasks(asyncio.get_running_loop()):
        if task is not asyncio.current_task():
            # info
            task.print_stack()

            if task.exception():
                assert type(task.exception()) in [ValueError, RuntimeError]

            assert task.done()
            assert not task.cancelled()


async def test_logged_gather_wo_raising(coros: list[Coroutine], mock_logger: mock.Mock):
    results = await logged_gather(*coros, reraise=False, log=mock_logger)

    assert results[0] == 0
    assert isinstance(results[1], ValueError)
    assert results[2] == 2
    assert isinstance(results[3], RuntimeError)
    assert isinstance(results[4], ValueError)
    assert results[5] == 5


@pytest.fixture()
async def coroutine_that_cancels() -> asyncio.Future | Awaitable:
    async def _self_cancelling() -> None:
        await asyncio.sleep(0)  # NOTE: this forces a context switch
        msg = "manual cancellation"
        raise asyncio.CancelledError(msg)

    return _self_cancelling()


async def test_fire_and_forget_cancellation_errors_raised_when_awaited(
    coroutine_that_cancels: Coroutine,
    faker: Faker,
):
    tasks_collection = set()
    task = fire_and_forget_task(
        coroutine_that_cancels,
        task_suffix_name=faker.pystr(),
        fire_and_forget_tasks_collection=tasks_collection,
    )
    assert task in tasks_collection
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task not in tasks_collection


async def test_fire_and_forget_cancellation_no_errors_raised(
    coroutine_that_cancels: Coroutine,
    faker: Faker,
):
    tasks_collection = set()
    task = fire_and_forget_task(
        coroutine_that_cancels,
        task_suffix_name=faker.pystr(),
        fire_and_forget_tasks_collection=tasks_collection,
    )
    assert task in tasks_collection
    await asyncio.sleep(1)
    assert task.cancelled() is True
    assert task not in tasks_collection


async def test_fire_and_forget_1000s_tasks(faker: Faker):
    tasks_collection = set()

    async def _some_task(n: int) -> str:
        await asyncio.sleep(faker.random_int(1, 3))
        return f"I'm great since I slept a bit, and by the way I'm task {n}"

    for n in range(1000):
        fire_and_forget_task(
            _some_task(n),
            task_suffix_name=f"{faker.pystr()}_{n}",
            fire_and_forget_tasks_collection=tasks_collection,
        )
    assert len(tasks_collection) == 1000
    done, pending = await asyncio.wait(
        tasks_collection, timeout=10, return_when=asyncio.ALL_COMPLETED
    )
    assert len(done) == 1000
    assert len(pending) == 0
    assert len(tasks_collection) == 0


@pytest.mark.parametrize(
    "original, termination, expected",
    [
        ("hello", "world", "helloworld"),
        ("first_second", "second", "first_second"),
        ("some/path", "/", "some/path/"),
    ],
)
def test_ensure_ends_with(original: str, termination: str, expected: str):
    original_copy = copy(original)
    terminated_string = ensure_ends_with(original, termination)
    assert original_copy == original
    assert terminated_string.endswith(termination)
    assert terminated_string == expected


@pytest.fixture
def uids(faker: Faker) -> list[int]:
    return [faker.pyint() for _ in range(10)]


@pytest.fixture
def long_delay() -> int:
    return 10


@pytest.fixture
def slow_successful_coros_list(uids: list[int], long_delay: int) -> list[Coroutine]:
    return [_succeed(uid, delay=long_delay) for uid in uids]


@pytest.fixture
def successful_coros_list(uids: list[int]) -> list[Coroutine]:
    return [_succeed(uid) for uid in uids]


@pytest.fixture
async def successful_coros_gen(uids: list[int]) -> AsyncIterator[Coroutine]:
    async def as_async_iter(it):
        for x in it:
            yield x

    return as_async_iter(_succeed(uid) for uid in uids)


@pytest.fixture(params=["list", "generator"])
async def successful_coros(
    successful_coros_list: list[Coroutine],
    successful_coros_gen: AsyncIterator[Coroutine],
    request: pytest.FixtureRequest,
) -> list[Coroutine] | AsyncIterator[Coroutine]:
    return successful_coros_list if request.param == "list" else successful_coros_gen


@pytest.mark.parametrize("limit", [0, 2, 5, 10])
async def test_limited_as_completed(
    uids: list[int],
    successful_coros: list[Coroutine] | AsyncIterator[Coroutine],
    limit: int,
):
    expected_uids = deepcopy(uids)
    async for future in limited_as_completed(successful_coros, limit=limit):
        result = await future
        assert result is not None
        assert result in expected_uids
        expected_uids.remove(result)
    assert len(expected_uids) == 0


async def test_limited_as_completed_empty_coros():
    results = [await result async for result in limited_as_completed([])]
    assert results == []


@pytest.mark.parametrize("limit", [0, 2, 5, 10])
async def test_limited_gather_limits(
    uids: list[int],
    successful_coros_list: list[Coroutine],
    limit: int,
):
    results = await limited_gather(*successful_coros_list, limit=limit)
    assert results == uids


async def test_limited_gather(
    coros: list[Coroutine],
    mock_logger: mock.Mock,
):
    with pytest.raises(RuntimeError) as excinfo:
        await limited_gather(*coros, reraise=True, log=mock_logger, limit=0)

    # NOTE: #3 fails first
    assert "task#3" in str(excinfo.value)

    # NOTE: only first error in the list is raised, since it is not RuntimeError, that task
    assert isinstance(excinfo.value, RuntimeError)

    unfinished_tasks = [
        task
        for task in asyncio.all_tasks(asyncio.get_running_loop())
        if task is not asyncio.current_task()
    ]
    final_results = await asyncio.gather(*unfinished_tasks, return_exceptions=True)
    for result in final_results:
        if isinstance(result, Exception):
            assert isinstance(result, ValueError | RuntimeError)


async def test_limited_gather_wo_raising(
    coros: list[Coroutine], mock_logger: mock.Mock
):
    results = await limited_gather(*coros, reraise=False, log=mock_logger, limit=0)

    assert results[0] == 0
    assert isinstance(results[1], ValueError)
    assert results[2] == 2
    assert isinstance(results[3], RuntimeError)
    assert isinstance(results[4], ValueError)
    assert results[5] == 5


async def test_limited_gather_cancellation(slow_successful_coros_list: list[Coroutine]):
    task = asyncio.create_task(limited_gather(*slow_successful_coros_list, limit=0))
    await asyncio.sleep(3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # check all coros are cancelled
    unfinished_tasks = [
        task
        for task in asyncio.all_tasks(asyncio.get_running_loop())
        if task is not asyncio.current_task()
    ]
    assert not unfinished_tasks
