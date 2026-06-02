# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from fastapi import FastAPI
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.redis import RedisSettings


async def test_redis_module_initializes_and_shuts_down(
    configure_registry_caching: EnvVarsDict,
    configure_registry_redis_backend: EnvVarsDict,
    use_in_memory_redis: RedisSettings,
    app: FastAPI,
): ...
