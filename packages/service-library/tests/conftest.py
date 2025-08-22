# pylint: disable=contextmanager-generator-missing-cleanup
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
from servicelib.redis import RedisClientSDK, RedisClientsManager, RedisManagerDBConfig
from settings_library.redis import RedisDatabase, RedisSettings

pytest_plugins = [
    "pytest_simcore.asyncio_event_loops",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.docker",
    "pytest_simcore.environment_configs",
    "pytest_simcore.file_extra",
    "pytest_simcore.logging",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.simcore_service_library_fixtures",
]


@pytest.fixture(scope="session")
def package_tests_dir():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def package_dir() -> Path:
    pdir = Path(servicelib.__file__).resolve().parent
    assert pdir.exists()
    return pdir


@pytest.fixture(scope="session")
def osparc_simcore_root_dir(package_tests_dir: Path) -> Path:
    root_dir = package_tests_dir.parent.parent.parent.resolve()
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any(
        root_dir.glob("packages/service-library")
    ), f"{root_dir} not look like rootdir"
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


@asynccontextmanager
async def _get_redis_client_sdk(
    redis_settings: RedisSettings,
) -> AsyncIterator[
    Callable[[RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]]
]:
    @asynccontextmanager
    async def _(
        database: RedisDatabase,
        decode_response: bool = True,  # noqa: FBT002
    ) -> AsyncIterator[RedisClientSDK]:
        redis_resources_dns = redis_settings.build_redis_dsn(database)
        client = RedisClientSDK(
            redis_resources_dns, decode_responses=decode_response, client_name="pytest"
        )
        await client.setup()
        assert client
        assert client.redis_dsn == redis_resources_dns
        assert client.client_name == "pytest"

        yield client

        await client.shutdown()

    async def _cleanup_redis_data(clients_manager: RedisClientsManager) -> None:
        for db in RedisDatabase:
            await clients_manager.client(db).redis.flushall()

    async with RedisClientsManager(
        {RedisManagerDBConfig(database=db) for db in RedisDatabase},
        redis_settings,
        client_name="pytest",
    ) as clients_manager:
        await _cleanup_redis_data(clients_manager)
        yield _
        await _cleanup_redis_data(clients_manager)


@pytest.fixture
async def get_redis_client_sdk(
    mock_redis_socket_timeout: None, use_in_memory_redis: RedisSettings
) -> AsyncIterable[
    Callable[[RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]]
]:
    async with _get_redis_client_sdk(use_in_memory_redis) as client:
        yield client


@pytest.fixture
async def get_in_process_redis_client_sdk(
    mock_redis_socket_timeout: None, redis_service: RedisSettings
) -> AsyncIterable[
    Callable[[RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]]
]:
    async with _get_redis_client_sdk(redis_service) as client:
        yield client
