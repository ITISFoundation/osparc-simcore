import datetime
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager

import pytest
from faker import Faker
from pytest_mock import MockerFixture
from servicelib.redis import _constants as redis_constants
from servicelib.redis._client import RedisClientSDK
from settings_library.redis import RedisDatabase


@pytest.fixture
async def redis_client_sdk(
    get_in_process_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ],
) -> AsyncIterator[RedisClientSDK]:
    async with get_in_process_redis_client_sdk(RedisDatabase.RESOURCES) as client:
        yield client


@pytest.fixture
def lock_name(faker: Faker) -> str:
    return faker.pystr()


@pytest.fixture
def with_short_default_redis_lock_ttl(mocker: MockerFixture) -> datetime.timedelta:
    short_ttl = datetime.timedelta(seconds=0.25)
    mocker.patch.object(redis_constants, "DEFAULT_LOCK_TTL", short_ttl)
    return short_ttl
