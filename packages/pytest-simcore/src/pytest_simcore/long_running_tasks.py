# pylint: disable=unused-argument

import functools

import pytest
from pytest_mock import MockerFixture
from servicelib.long_running_tasks import task
from servicelib.long_running_tasks._store.in_memory import InMemoryStore


def _mock_decorator_with_args(*decorator_args, **decorator_kwargs):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*func_args, **func_kwargs):
            return await func(*func_args, **func_kwargs)

        return wrapper

    return decorator


@pytest.fixture
def use_in_memory_long_running_tasks(mocker: MockerFixture) -> None:
    mocker.patch.object(task, "RedisStore", InMemoryStore)
    # for testing the exclsive is not required so it's disabled
    mocker.patch.object(task, "exclusive", _mock_decorator_with_args)
