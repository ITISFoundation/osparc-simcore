import pytest
from servicelib.long_running_tasks import task
from servicelib.long_running_tasks._store.in_memory import InMemoryStore


@pytest.fixture
def uese_in_memory_lonng_running_tasks_storage() -> None:
    task._StorageClass = InMemoryStore  # pylint:disable=protected-access
