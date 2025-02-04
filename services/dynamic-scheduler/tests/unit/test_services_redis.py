# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


import pytest
from fastapi import FastAPI
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.redis import get_all_redis_clients

pytest_simcore_core_services_selection = [
    "redis",
]


@pytest.fixture
def app_environment(
    disable_rabbitmq_lifespan: None,
    disable_deferred_manager_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    app_environment: EnvVarsDict,
    redis_service: RedisSettings,
) -> EnvVarsDict:
    return app_environment


async def test_health(app: FastAPI):
    redis_clients = get_all_redis_clients(app)
    for redis_client in redis_clients.values():
        assert await redis_client.ping() is True
