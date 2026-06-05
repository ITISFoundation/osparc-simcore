# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest import mock

from fastapi import FastAPI
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.redis import RedisSettings
from simcore_service_director.modules.redis import get_redis_client_manager


async def test_redis_module_initializes_and_shuts_down(
    configure_registry_access: EnvVarsDict,
    configure_registry_caching: EnvVarsDict,
    configure_registry_redis_backend: EnvVarsDict,
    with_disabled_auto_caching_task: mock.Mock,
    use_in_memory_redis: RedisSettings,
    app: FastAPI,
    app_settings: EnvVarsDict,
):
    get_redis_client_manager(app)  # should not raise
