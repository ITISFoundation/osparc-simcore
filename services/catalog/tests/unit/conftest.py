# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import hashlib
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
import simcore_service_catalog
import yaml
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI, status
from packaging.version import Version
from pytest_mock import MockerFixture
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
def director_service_openapi_specs(
    osparc_simcore_services_dir: Path,
) -> dict[str, Any]:
    openapi_path = (
        osparc_simcore_services_dir
        / "director"
        / "src"
        / "simcore_service_director"
        / "api"
        / "v0"
        / "openapi.yaml"
    )
    return yaml.safe_load(openapi_path.read_text())


@pytest.fixture
def expected_director_list_services() -> list[dict[str, Any]]:
    """This fixture has at least TWO purposes:

    1. can be used as a reference to check the results at the other end
    2. can be used to change responses of the director API downstream (override fixture)

    """
    return [
        {
            "image_digest": hashlib.sha256(
                f"simcore/services/comp/ans-model:{major}".encode()
            ).hexdigest(),
            "authors": [
                {
                    "name": "John Smith",
                    "email": "smith@acme.com",
                    "affiliation": "ACME",
                }
            ],
            "contact": "smith@acme.com",
            "description": "Autonomous Nervous System Network model",
            "inputs": {
                "input_1": {
                    "displayOrder": 1,
                    "label": "Simulation time",
                    "description": "Duration of the simulation",
                    "type": "ref_contentSchema",
                    "contentSchema": {
                        "type": "number",
                        "x_unit": "milli-second",
                    },
                    "defaultValue": 2,
                }
            },
            "integration-version": "1.0.0",
            "key": "simcore/services/comp/ans-model",
            "name": "Autonomous Nervous System Network model",
            "outputs": {
                "output_1": {
                    "displayOrder": 1,
                    "label": "ANS output",
                    "description": "Output of simulation of Autonomous Nervous System Network model",
                    "type": "data:*/*",
                    "fileToKeyMap": {"ANS_output.txt": "output_1"},
                },
                "output_2": {
                    "displayOrder": 2,
                    "label": "Stimulation parameters",
                    "description": "stim_param.txt file containing the input provided in the inputs port",
                    "type": "data:*/*",
                    "fileToKeyMap": {"ANS_stim_param.txt": "output_2"},
                },
            },
            "thumbnail": "https://www.statnews.com/wp-content/uploads/2020/05/3D-rat-heart.-iScience--768x432.png",
            "type": "computational",
            "version": f"{major}.0.0",
        }
        for major in range(1, 4)
    ]


@pytest.fixture
def mocked_director_service_api(
    app_settings: ApplicationSettings,
    director_service_openapi_specs: dict[str, Any],
    expected_director_list_services: list[dict[str, Any]],
) -> Iterator[respx.MockRouter]:
    assert app_settings.CATALOG_DIRECTOR
    with respx.mock(
        base_url=app_settings.CATALOG_DIRECTOR.base_url,  # NOTE: it include v0/
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:

        # NOTE: this MUST be in sync with services/director/src/simcore_service_director/api/v0/openapi.yaml
        openapi = deepcopy(director_service_openapi_specs)
        assert Version(openapi["info"]["version"]) == Version("0.1.0")

        # Validate responses against OAS
        respx_mock.head("/", name="healthcheck").respond(
            200,
            json={
                "data": {
                    "name": "simcore-service-director",
                    "status": "SERVICE_RUNNING",
                    "api_version": "0.1.0",
                    "version": "0.1.0",
                }
            },
        )

        @respx_mock.get(
            path__regex=r"/services$",
            name="list_services",
        )
        def list_services(request):
            return httpx.Response(
                status.HTTP_200_OK, json={"data": expected_director_list_services}
            )

        @respx_mock.get(
            path__regex=r"/services/(?P<service_key>[/\w-]+)/(?P<service_version>[0-9.]+)$",
            name="get_service",
        )
        def get_service(request, service_key, service_version):
            for service in expected_director_list_services:
                if (
                    service["key"] == service_key
                    and service["version"] == service_version
                ):
                    single_service_list = [
                        service,
                    ]  # NOTE: this is a defect in director's API
                    return httpx.Response(
                        status.HTTP_200_OK, json={"data": single_service_list}
                    )
            return httpx.Response(
                status.HTTP_404_NOT_FOUND, json={"error": "Service not found"}
            )

        # @respx_mock.get(
        #     path__regex=r"/services/(?P<service_key>[/\w-]+)/(?P<service_version>[0-9\.]+)/labels$", name="get_service_labels"
        # )
        # def get_service_labels(request):
        #     raise NotImplementedError

        # @respx_mock.get(
        #     path__regex=r"/services_extras/(?P<service_key>[/\w-]+)/(?P<service_version>[0-9\.]+)$", name="get_service_extras"
        # )
        # def get_service_extras(request):
        #     raise NotImplementedError

        yield respx_mock
