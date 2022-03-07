# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
from pathlib import Path

import pytest
from servicelib.utils import logged_gather


async def _value_error(uid, *, delay=1):
    await _succeed(delay)
    raise ValueError(f"task#{uid}")


async def _runtime_error(uid, *, delay=1):
    await _succeed(delay)
    raise RuntimeError(f"task#{uid}")


async def _succeed(uid, *, delay=1):
    print(f"task#{uid} begin")
    await asyncio.sleep(delay)
    print(f"task#{uid} end")
    return uid


@pytest.fixture
def coros():
    coros = [
        _succeed(0),
        _value_error(1, delay=2),
        _succeed(2),
        _runtime_error(3),
        _value_error(4, delay=0),
        _succeed(5),
    ]
    return coros


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

    with pytest.raises(ValueError) as excinfo:
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
