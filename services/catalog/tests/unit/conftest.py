# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from pathlib import Path

import pytest
import respx
import simcore_service_catalog
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from pytest_mock import MockerFixture
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from simcore_service_catalog.core.application import create_app
from simcore_service_catalog.core.settings import ApplicationSettings

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.faker_products_data",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.postgres_service",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "catalog"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_catalog"))
    return service_folder


@pytest.fixture(scope="session")
def package_dir() -> Path:
    """Notice that this might be under src (if installed as edit mode)
    or in the installation folder
    """
    dirpath = Path(simcore_service_catalog.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def env_devel_dict(
    env_devel_dict: EnvVarsDict, external_envfile_dict: EnvVarsDict
) -> EnvVarsDict:
    if external_envfile_dict:
        assert "CATALOG_DEV_FEATURES_ENABLED" in external_envfile_dict
        assert "CATALOG_SERVICES_DEFAULT_RESOURCES" in external_envfile_dict
        return external_envfile_dict
    return env_devel_dict


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    docker_compose_service_environment_dict: EnvVarsDict,
) -> EnvVarsDict:
    """Produces testing environment for the app
    by replicating the environment defined in the docker-compose
    when initialized with .env-devel
    """
    return setenvs_from_dict(
        monkeypatch,
        {**docker_compose_service_environment_dict},
    )


MAX_TIME_FOR_APP_TO_STARTUP = 10
MAX_TIME_FOR_APP_TO_SHUTDOWN = 10


@pytest.fixture
def app_settings(app_environment: EnvVarsDict) -> ApplicationSettings:
    assert app_environment
    return ApplicationSettings.create_from_envs()


@pytest.fixture
async def app(
    app_settings: ApplicationSettings, is_pdb_enabled: bool
) -> AsyncIterator[FastAPI]:
    assert app_environment
    the_test_app = create_app(settings=app_settings)
    async with LifespanManager(
        the_test_app,
        startup_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_STARTUP,
        shutdown_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_SHUTDOWN,
    ):
        yield the_test_app


@pytest.fixture
def service_caching_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIOCACHE_DISABLE", "1")


@pytest.fixture
def postgres_setup_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CATALOG_POSTGRES", "null")


#
# rabbit-MQ
#


@pytest.fixture
def setup_rabbitmq_and_rpc_disabled(mocker: MockerFixture):
    # The following services are affected if rabbitmq is not in place
    mocker.patch("simcore_service_catalog.core.application.setup_rabbitmq")
    mocker.patch("simcore_service_catalog.core.application.setup_rpc_api_routes")


@pytest.fixture
async def rpc_client(
    faker: Faker, rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]]
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client(f"catalog-client-{faker.word()}")


#
# director
#


@pytest.fixture
def director_setup_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CATALOG_DIRECTOR", "null")


@pytest.fixture
def mocked_director_service_api(
    app_settings: ApplicationSettings,
) -> Iterator[respx.MockRouter]:
    assert app_settings.CATALOG_DIRECTOR
    with respx.mock(
        base_url=app_settings.CATALOG_DIRECTOR.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.head("/", name="healthcheck").respond(200, json={"health": "OK"})
        respx_mock.get("/services", name="list_services").respond(
            200, json={"data": ["one", "two"]}
        )

        yield respx_mock
