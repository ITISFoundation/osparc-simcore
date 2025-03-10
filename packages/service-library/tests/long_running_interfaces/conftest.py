from datetime import timedelta

import pytest
from servicelib.long_running_interfaces._models import JobUniqueId, LongRunningNamespace


@pytest.fixture
def long_running_namespace() -> LongRunningNamespace:
    return "test_namespace"


@pytest.fixture
def unique_id() -> JobUniqueId:
    return "test_id"


@pytest.fixture
def job_timeout() -> timedelta:
    return timedelta(seconds=1)
