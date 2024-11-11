# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import sys
from collections.abc import AsyncIterable, AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import servicelib
from faker import Faker
from pytest_mock import MockerFixture
from servicelib.redis import RedisClientSDK, RedisClientsManager, RedisManagerDBConfig
from settings_library.redis import RedisDatabase, RedisSettings

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.docker",
    "pytest_simcore.environment_configs",
    "pytest_simcore.file_extra",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.simcore_service_library_fixtures",
]


@pytest.fixture(scope="session")
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def package_dir() -> Path:
    pdir = Path(servicelib.__file__).resolve().parent
    assert pdir.exists()
    return pdir


@pytest.fixture(scope="session")
def osparc_simcore_root_dir(here) -> Path:
    root_dir = here.parent.parent.parent.resolve()
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any(root_dir.glob("packages/service-library")), (
        "%s not look like rootdir" % root_dir
    )
    return root_dir


@pytest.fixture
def fake_data_dict(faker: Faker) -> dict[str, Any]:
    data = {
        "uuid_as_UUID": faker.uuid4(cast_to=None),
        "uuid_as_str": faker.uuid4(),
        "int": faker.pyint(),
        "float": faker.pyfloat(),
        "str": faker.pystr(),
    }
    data["object"] = deepcopy(data)
    return data


@pytest.fixture
async def get_redis_client_sdk(
    mock_redis_socket_timeout: None,
    mocker: MockerFixture,
    redis_service: RedisSettings,
) -> AsyncIterable[
    Callable[[RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]]
]:
    @asynccontextmanager
    async def _(
        database: RedisDatabase, decode_response: bool = True  # noqa: FBT002
    ) -> AsyncIterator[RedisClientSDK]:
        redis_resources_dns = redis_service.build_redis_dsn(database)
        client = RedisClientSDK(
            redis_resources_dns, decode_responses=decode_response, client_name="pytest"
        )
        assert client
        assert client.redis_dsn == redis_resources_dns
        assert client.client_name == "pytest"
        await client.setup()

        yield client

        await client.shutdown()

    async def _cleanup_redis_data(clients_manager: RedisClientsManager) -> None:
        for db in RedisDatabase:
            await clients_manager.client(db).redis.flushall()

    async with RedisClientsManager(
        {RedisManagerDBConfig(db) for db in RedisDatabase},
        redis_service,
        client_name="pytest",
    ) as clients_manager:
        await _cleanup_redis_data(clients_manager)
        yield _
        await _cleanup_redis_data(clients_manager)


@pytest.fixture()
def uninstrument_opentelemetry():
    yield
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().uninstrument()
    except ImportError:
        pass
    try:
        from opentelemetry.instrumentation.botocore import BotocoreInstrumentor

        BotocoreInstrumentor().uninstrument()
    except ImportError:
        pass
    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        RequestsInstrumentor().uninstrument()
    except ImportError:
        pass
    try:
        from opentelemetry.instrumentation.aiopg import AiopgInstrumentor

        AiopgInstrumentor().uninstrument()
    except ImportError:
        pass
    try:
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

        AsyncPGInstrumentor().uninstrument()
    except ImportError:
        pass
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor().uninstrument()
    except ImportError:
        pass
    try:
        from opentelemetry.instrumentation.aiohttp_client import (
            AioHttpClientInstrumentor,
        )

        AioHttpClientInstrumentor().uninstrument()
    except ImportError:
        pass
    try:
        from opentelemetry.instrumentation.aiohttp_server import (
            AioHttpServerInstrumentor,
        )

        AioHttpServerInstrumentor().uninstrument()
    except ImportError:
        pass
