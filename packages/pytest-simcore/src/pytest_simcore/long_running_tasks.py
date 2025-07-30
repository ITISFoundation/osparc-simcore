import pytest
from fakeredis import FakeAsyncRedis
from pytest_mock import MockerFixture
from servicelib.redis import _client


@pytest.fixture
async def use_in_memory_redis(mocker: MockerFixture) -> None:
    mocker.patch.object(_client, "aioredis", FakeAsyncRedis)
