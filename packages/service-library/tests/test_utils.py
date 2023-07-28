# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
from collections.abc import Awaitable, Coroutine
from copy import copy
from pathlib import Path
from random import randint
from typing import Any

import pytest
from faker import Faker
from servicelib.utils import (
    ensure_ends_with,
    fire_and_forget_task,
    logged_gather,
    partition_gen,
)


async def _value_error(uid, *, delay=1):
    await _succeed(delay)
    msg = f"task#{uid}"
    raise ValueError(msg)


async def _runtime_error(uid, *, delay=1):
    await _succeed(delay)
    msg = f"task#{uid}"
    raise RuntimeError(msg)


async def _succeed(uid, *, delay=1):
    print(f"task#{uid} begin")
    await asyncio.sleep(delay)
    print(f"task#{uid} end")
    return uid


@pytest.fixture
def coros():
    return [
        _succeed(0),
        _value_error(1, delay=2),
        _succeed(2),
        _runtime_error(3),
        _value_error(4, delay=0),
        _succeed(5),
    ]


@pytest.fixture
def mock_logger(mocker):
    mock_logger = mocker.Mock()

    yield mock_logger

    assert mock_logger.mock_calls
    mock_logger.warning.assert_called()
    assert (
        len(mock_logger.warning.mock_calls) == 3
    ), "Expected all 3 errors ALWAYS logged as warnings"


async def test_logged_gather(event_loop, coros, mock_logger):
    with pytest.raises(ValueError) as excinfo:  # noqa: PT011
        await logged_gather(*coros, reraise=True, log=mock_logger)

    # NOTE: #4 fails first, the one raised in #1
    assert "task#1" in str(excinfo.value)

    # NOTE: only first error in the list is raised, since it is not RuntimeError, that task
    assert isinstance(excinfo.value, ValueError)

    for task in asyncio.all_tasks(event_loop):
        if task is not asyncio.current_task():
            # info
            task.print_stack()

            if task.exception():
                assert type(task.exception()) in [ValueError, RuntimeError]

            assert task.done()
            assert not task.cancelled()


async def test_logged_gather_wo_raising(coros, mock_logger):
    results = await logged_gather(*coros, reraise=False, log=mock_logger)

    assert results[0] == 0
    assert isinstance(results[1], ValueError)
    assert results[2] == 2
    assert isinstance(results[3], RuntimeError)
    assert isinstance(results[4], ValueError)
    assert results[5] == 5


def print_tree(path: Path, level=0):
    tab = " " * level
    print(f"{tab}{'+' if path.is_dir() else '-'} {path if level==0 else path.name}")
    for p in path.glob("*"):
        print_tree(p, level + 1)


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

    async def _some_task(n: int):
        await asyncio.sleep(randint(1, 3))
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


@pytest.mark.parametrize(
    "slice_size, input_list, expected, ",
    [
        pytest.param(
            5,
            list(range(13)),
            [(0, 1, 2, 3, 4), (5, 6, 7, 8, 9), (10, 11, 12)],
            id="group_5_last_group_is_smaller",
        ),
        pytest.param(
            2,
            list(range(5)),
            [(0, 1), (2, 3), (4,)],
            id="group_2_last_group_is_smaller",
        ),
        pytest.param(
            2,
            list(range(4)),
            [(0, 1), (2, 3)],
            id="group_2_last_group_is_the_same",
        ),
        pytest.param(
            10,
            list(range(4)),
            [(0, 1, 2, 3)],
            id="only_one_group_if_list_is_not_bit_enough",
        ),
        pytest.param(
            3,
            [],
            [()],
            id="input_is_empty_returns_an_empty_list",
        ),
        pytest.param(
            5,
            list(range(13)),
            [(0, 1, 2, 3, 4), (5, 6, 7, 8, 9), (10, 11, 12)],
            id="group_5_using_generator",
        ),
    ],
)
def test_partition_iter(
    input_list: list[Any], expected: list[tuple[Any, ...]], slice_size: int
):
    # check returned result
    result = list(partition_gen(input_list, slice_size=slice_size))
    assert result == expected

    # check returned type
    for entry in result:
        assert type(entry) == tuple
