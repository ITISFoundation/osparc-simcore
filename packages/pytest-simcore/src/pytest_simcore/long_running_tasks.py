import pytest
from pytest_mock import MockerFixture
from servicelib.long_running_tasks import task
from servicelib.long_running_tasks._store.in_memory import InMemoryStore


@pytest.fixture
def uese_in_memory_lonng_running_tasks_storage(mocker: MockerFixture) -> None:
    mocker.patch.object(task, "RedisStore", InMemoryStore)
