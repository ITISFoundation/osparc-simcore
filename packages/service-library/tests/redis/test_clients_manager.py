# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from servicelib.redis._clients_manager import RedisClientsManager
from servicelib.redis._models import RedisManagerDBConfig
from settings_library.redis import RedisDatabase, RedisSettings

pytest_simcore_core_services_selection = [
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


async def test_redis_client_sdks_manager(
    mock_redis_socket_timeout: None,
    redis_service: RedisSettings,
):
    all_redis_configs: set[RedisManagerDBConfig] = {
        RedisManagerDBConfig(database=db) for db in RedisDatabase
    }
    manager = RedisClientsManager(
        databases_configs=all_redis_configs,
        settings=redis_service,
        client_name="pytest",
    )

    async with manager:
        for config in all_redis_configs:
            assert manager.client(config.database)
