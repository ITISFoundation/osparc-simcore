# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from asgi_lifespan import LifespanManager
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.tracing import TracingConfig
from simcore_service_director._meta import APP_NAME
from simcore_service_director.core.application import create_app
from simcore_service_director.core.settings import ApplicationSettings


async def test_redis_module_starts_disabled_by_default(app_settings: ApplicationSettings):
    tracing_config = TracingConfig.create(service_name=APP_NAME, tracing_settings=None)
    app = create_app(settings=app_settings, tracing_config=tracing_config)

    async with LifespanManager(app):
        assert app.state.redis_clients_manager is None


async def test_redis_module_initializes_and_shuts_down(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
):
    set_up_called = False
    shut_down_called = False

    class _FakeRedisClientsManager:
        def __init__(self, **_kwargs):
            pass

        async def setup(self) -> None:
            nonlocal set_up_called
            set_up_called = True

        async def shutdown(self) -> None:
            nonlocal shut_down_called
            shut_down_called = True

    monkeypatch.setattr(
        "simcore_service_director.modules.redis.RedisClientsManager",
        _FakeRedisClientsManager,
    )

    setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "DIRECTOR_REGISTRY_CACHING": "True",
            "DIRECTOR_REDIS_CACHE_BACKEND": "redis",
            "DIRECTOR_REDIS": '{"REDIS_HOST": "redis", "REDIS_PORT": 6379}',
        },
    )
    settings = ApplicationSettings.create_from_envs()

    tracing_config = TracingConfig.create(service_name=APP_NAME, tracing_settings=None)
    app = create_app(settings=settings, tracing_config=tracing_config)

    async with LifespanManager(app):
        assert set_up_called is True

    assert shut_down_called is True
