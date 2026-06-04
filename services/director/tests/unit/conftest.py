# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import redis.asyncio as redis_asyncio
import simcore_service_director
from asgi_lifespan import LifespanManager
from fakeredis import FakeAsyncRedisConnection, FakeServer
from fastapi import FastAPI
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.tracing import TracingConfig
from settings_library.docker_registry import RegistrySettings
from settings_library.redis import RedisSettings
from simcore_service_director._meta import APP_NAME
from simcore_service_director.core.application import create_app
from simcore_service_director.core.settings import ApplicationSettings

pytest_plugins = [
    "fixtures.fake_services",
    "pytest_simcore.asyncio_event_loops",
    "pytest_simcore.cli_runner",
    "pytest_simcore.docker",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.faker_projects_data",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.logging",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.simcore_service_library_fixtures",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "director"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_director"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_director.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def common_schemas_specs_dir(osparc_simcore_root_dir: Path) -> Path:
    specs_dir = osparc_simcore_root_dir / "api" / "specs" / "director" / "schemas"
    assert specs_dir.exists()
    return specs_dir


@pytest.fixture
def configure_swarm_stack_name(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        envs={
            "SWARM_STACK_NAME": "test_stack",
        },
    )


@pytest.fixture
def configure_registry_access(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, docker_registry: str
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        envs={
            "REGISTRY_URL": docker_registry,
            "REGISTRY_PATH": docker_registry,
            "REGISTRY_SSL": False,
        },
    )


@pytest.fixture
def configure_external_registry_access(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    external_registry_settings: RegistrySettings | None,
) -> EnvVarsDict:
    assert external_registry_settings
    return app_environment | setenvs_from_dict(
        monkeypatch,
        envs={
            **external_registry_settings.model_dump(by_alias=True, exclude_none=True),
            "REGISTRY_PW": external_registry_settings.REGISTRY_PW.get_secret_value(),
        },
    )


@pytest.fixture(scope="session")
def configure_custom_registry(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    pytestconfig: pytest.Config,
) -> EnvVarsDict:
    # to set these values call
    # pytest --registry_url myregistry --registry_user username --registry_pw password
    registry_url = pytestconfig.getoption("registry_url")
    assert registry_url
    assert isinstance(registry_url, str)
    registry_user = pytestconfig.getoption("registry_user")
    assert registry_user
    assert isinstance(registry_user, str)
    registry_pw = pytestconfig.getoption("registry_pw")
    assert registry_pw
    assert isinstance(registry_pw, str)
    return app_environment | setenvs_from_dict(
        monkeypatch,
        envs={
            "REGISTRY_URL": registry_url,
            "REGISTRY_AUTH": True,
            "REGISTRY_USER": registry_user,
            "REGISTRY_PW": registry_pw,
            "REGISTRY_SSL": False,
        },
    )


@pytest.fixture
def configure_registry_caching(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(monkeypatch, {"DIRECTOR_REGISTRY_CACHING": True})


@pytest.fixture
def api_version_prefix() -> str:
    return "v0"


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    docker_compose_service_environment_dict: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_environment_dict,
            "DIRECTOR_TRACING": "null",
            "DIRECTOR_REGISTRY_CACHING": False,
        },
    )


MAX_TIME_FOR_APP_TO_STARTUP = 10
MAX_TIME_FOR_APP_TO_SHUTDOWN = 10


@pytest.fixture
def app_settings(app_environment: EnvVarsDict) -> ApplicationSettings:
    return ApplicationSettings.create_from_envs()


@pytest.fixture
async def app(app_settings: ApplicationSettings, is_pdb_enabled: bool) -> AsyncIterator[FastAPI]:
    tracing_config = TracingConfig.create(
        service_name=APP_NAME,
        tracing_settings=None,  # disable tracing in tests
    )
    the_test_app = create_app(settings=app_settings, tracing_config=tracing_config)
    async with LifespanManager(
        the_test_app,
        startup_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_STARTUP,
        shutdown_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_SHUTDOWN,
    ):
        yield the_test_app


@pytest.fixture
async def with_docker_network(
    docker_network: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    return await docker_network()


@pytest.fixture
def configured_docker_network(
    with_docker_network: dict[str, Any],
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {"DIRECTOR_SIMCORE_SERVICES_NETWORK_NAME": with_docker_network["Name"]},
    )


@pytest.fixture
def configure_registry_redis_backend(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "REDIS_USER": "null",
            "REDIS_PASSWORD": "null",
        },
    )


@pytest.fixture
def with_disabled_auto_caching_task(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director.modules.docker_registry._setup.refresh_all_services_cache",
        autospec=True,
    )


@pytest.fixture
def use_in_memory_redis(mocker: MockerFixture) -> RedisSettings:
    # Also patch the redis client of aiocache to use fakeredis,
    # so that the registry proxy tests can run without a real Redis server
    fake_server = FakeServer()
    OriginalPool = redis_asyncio.ConnectionPool

    def fake_connection_pool(*args, **kwargs) -> redis_asyncio.ConnectionPool:
        kwargs["connection_class"] = FakeAsyncRedisConnection
        kwargs["server"] = fake_server
        return OriginalPool(*args, **kwargs)

    mocker.patch(
        "redis.asyncio.from_url",
        lambda *a, **kw: redis_asyncio.Redis(  # noqa: ARG005
            connection_pool=fake_connection_pool(**kw),
        ),
    )
    mocker.patch("redis.asyncio.ConnectionPool", fake_connection_pool)
    return RedisSettings()
