# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import hashlib
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any, NamedTuple

import httpx
import pytest
import respx
import simcore_service_catalog
import simcore_service_catalog.core.events
import yaml
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from packaging.version import Version
from pydantic import EmailStr
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from simcore_service_catalog.core.application import create_app
from simcore_service_catalog.core.settings import ApplicationSettings

pytest_plugins = [
    "pytest_simcore.cli_runner",
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
        {
            **docker_compose_service_environment_dict,
            "CATALOG_TRACING": "null",
        },
    )


MAX_TIME_FOR_APP_TO_STARTUP = 10
MAX_TIME_FOR_APP_TO_SHUTDOWN = 10


@pytest.fixture
def app_settings(app_environment: EnvVarsDict) -> ApplicationSettings:
    assert app_environment
    return ApplicationSettings.create_from_envs()


class AppLifeSpanSpyTargets(NamedTuple):
    on_startup: MockType
    on_shutdown: MockType


@pytest.fixture
def spy_app(mocker: MockerFixture) -> AppLifeSpanSpyTargets:
    # Used to ensure startup/teardown workflows using different fixtures
    # work as expected
    return AppLifeSpanSpyTargets(
        on_startup=mocker.spy(
            simcore_service_catalog.core.events,
            "_flush_started_banner",
        ),
        on_shutdown=mocker.spy(
            simcore_service_catalog.core.events,
            "_flush_finished_banner",
        ),
    )


@pytest.fixture
async def app(
    app_settings: ApplicationSettings,
    is_pdb_enabled: bool,
    spy_app: AppLifeSpanSpyTargets,
) -> AsyncIterator[FastAPI]:
    """
    NOTE that this app was started when the fixture is setup
    and shutdown when the fixture is tear-down
    """

    # create instance
    assert app_environment
    app_under_test = create_app(settings=app_settings)

    assert spy_app.on_startup.call_count == 0
    assert spy_app.on_shutdown.call_count == 0

    async with LifespanManager(
        app_under_test,
        startup_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_STARTUP,
        shutdown_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_SHUTDOWN,
    ):
        assert spy_app.on_startup.call_count == 1
        assert spy_app.on_shutdown.call_count == 0

        yield app_under_test

    assert spy_app.on_startup.call_count == 1
    assert spy_app.on_shutdown.call_count == 1


@pytest.fixture
def client(
    app_settings: ApplicationSettings, spy_app: AppLifeSpanSpyTargets
) -> Iterator[TestClient]:
    # NOTE: DO NOT add `app` as a dependency since it is already initialized

    # create instance
    assert app_environment
    app_under_test = create_app(settings=app_settings)

    assert (
        spy_app.on_startup.call_count == 0
    ), "TIP: Remove dependencies from `app` fixture and get it via `client.app`"
    assert spy_app.on_shutdown.call_count == 0

    with TestClient(app_under_test) as cli:

        assert spy_app.on_startup.call_count == 1
        assert spy_app.on_shutdown.call_count == 0

        yield cli

    assert spy_app.on_startup.call_count == 1
    assert spy_app.on_shutdown.call_count == 1


@pytest.fixture
async def aclient(
    app: FastAPI, spy_app: AppLifeSpanSpyTargets
) -> AsyncIterator[httpx.AsyncClient]:
    # NOTE: Avoids TestClient since `app` fixture already runs LifespanManager
    # Otherwise `with TestClient` will call twice start/shutdown events

    assert spy_app.on_startup.call_count == 1
    assert spy_app.on_shutdown.call_count == 0

    async with httpx.AsyncClient(
        base_url="http://catalog.testserver.io",
        headers={"Content-Type": "application/json"},
        transport=httpx.ASGITransport(app=app),
    ) as acli:
        assert isinstance(acli._transport, httpx.ASGITransport)
        assert spy_app.on_startup.call_count == 1
        assert spy_app.on_shutdown.call_count == 0

        yield acli

    assert spy_app.on_startup.call_count == 1
    assert spy_app.on_shutdown.call_count == 0


@pytest.fixture
def service_caching_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIOCACHE_DISABLE", "1")


@pytest.fixture
def postgres_setup_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CATALOG_POSTGRES", "null")


@pytest.fixture
def background_tasks_setup_disabled(mocker: MockerFixture) -> None:
    """patch the setup of the background task so we can call it manually"""

    def _factory(name):
        async def _side_effect(app: FastAPI):
            assert app
            print(
                "TEST",
                background_tasks_setup_disabled.__name__,
                "Disabled background tasks. Skipping execution of",
                name,
            )

        return _side_effect

    for name in ("start_registry_sync_task", "stop_registry_sync_task"):
        mocker.patch(
            f"simcore_service_catalog.core.events.{name}",
            side_effect=_factory(name),
            autospec=True,
        )


#
# rabbit-MQ
#


@pytest.fixture
def rabbitmq_and_rpc_setup_disabled(mocker: MockerFixture):
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
def expected_director_list_services(
    user_email: EmailStr, user_first_name: str, user_last_name: str
) -> list[dict[str, Any]]:
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
                    "name": f"{user_first_name} {user_last_name}",
                    "email": user_email,
                    "affiliation": "ACME",
                }
            ],
            "contact": user_email,
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
def mocked_director_service_api_base(
    app_settings: ApplicationSettings,
    director_service_openapi_specs: dict[str, Any],
) -> Iterator[respx.MockRouter]:
    """
    BASIC fixture to mock director service API

    Use `mocked_director_service_api_base` to customize the mocks

    """
    assert (
        app_settings.CATALOG_DIRECTOR
    ), "Check dependency on fixture `director_setup_disabled`"

    # NOTE: this MUST be in sync with services/director/src/simcore_service_director/api/v0/openapi.yaml
    openapi = director_service_openapi_specs
    assert Version(openapi["info"]["version"]) == Version("0.1.0")

    with respx.mock(
        base_url=app_settings.CATALOG_DIRECTOR.base_url,  # NOTE: it include v0/
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:

        # HEATHCHECK
        assert openapi["paths"].get("/")
        respx_mock.head("/", name="healthcheck").respond(
            status.HTTP_200_OK,
            json={
                "data": {
                    "name": "simcore-service-director",
                    "status": "SERVICE_RUNNING",
                    "api_version": "0.1.0",
                    "version": "0.1.0",
                }
            },
        )

        yield respx_mock


@pytest.fixture
def mocked_director_service_api(
    mocked_director_service_api_base: respx.MockRouter,
    director_service_openapi_specs: dict[str, Any],
    expected_director_list_services: list[dict[str, Any]],
) -> respx.MockRouter:
    """
    STANDARD fixture to mock director service API

    To customize the  mock responses use `mocked_director_service_api_base` instead
    """
    # alias
    openapi = director_service_openapi_specs
    respx_mock = mocked_director_service_api_base

    def _search(service_key, service_version):
        try:
            return next(
                s
                for s in expected_director_list_services
                if (s["key"] == service_key and s["version"] == service_version)
            )
        except StopIteration:
            return None

    # LIST
    assert openapi["paths"].get("/services")

    respx_mock.get(path__regex=r"/services$", name="list_services").respond(
        status.HTTP_200_OK, json={"data": expected_director_list_services}
    )

    # GET
    assert openapi["paths"].get("/services/{service_key}/{service_version}")

    @respx_mock.get(
        path__regex=r"^/services/(?P<service_key>[/\w-]+)/(?P<service_version>[0-9.]+)$",
        name="get_service",
    )
    def _get_service(request, service_key, service_version):
        if found := _search(service_key, service_version):
            # NOTE: this is a defect in director's API
            single_service_list = [found]
            return httpx.Response(
                status.HTTP_200_OK, json={"data": single_service_list}
            )
        return httpx.Response(
            status.HTTP_404_NOT_FOUND,
            json={
                "data": {
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": f"The service {service_key}:{service_version}  does not exist",
                }
            },
        )

    # GET LABELS
    assert openapi["paths"].get("/services/{service_key}/{service_version}/labels")

    @respx_mock.get(
        path__regex=r"^/services/(?P<service_key>[/\w-]+)/(?P<service_version>[0-9\.]+)/labels$",
        name="get_service_labels",
    )
    def _get_service_labels(request, service_key, service_version):
        if found := _search(service_key, service_version):
            return httpx.Response(
                status_code=status.HTTP_200_OK,
                json={
                    "data": {
                        "io.simcore.authors": '{"authors": [{"name": "John Smith", "email": "john@acme.com", "affiliation": "ACME\'IS Foundation"}]}',
                        "io.simcore.contact": '{"contact": "john@acme.com"}',
                        "io.simcore.description": '{"description": "Autonomous Nervous System Network model"}',
                        "io.simcore.inputs": '{"inputs": {"input_1": {"displayOrder": 1.0, "label": "Simulation time", "description": "Duration of the simulation", "type": "ref_contentSchema", "contentSchema": {"type": "number", "x_unit": "milli-second"}, "defaultValue": 2.0}}}',
                        "io.simcore.integration-version": '{"integration-version": "1.0.0"}',
                        "io.simcore.key": '{"key": "xxxxx"}'.replace(
                            "xxxxx", found["key"]
                        ),
                        "io.simcore.name": '{"name": "Autonomous Nervous System Network model"}',
                        "io.simcore.outputs": '{"outputs": {"output_1": {"displayOrder": 1.0, "label": "ANS output", "description": "Output of simulation of Autonomous Nervous System Network model", "type": "data:*/*", "fileToKeyMap": {"ANS_output.txt": "output_1"}}, "output_2": {"displayOrder": 2.0, "label": "Stimulation parameters", "description": "stim_param.txt file containing the input provided in the inputs port", "type": "data:*/*", "fileToKeyMap": {"ANS_stim_param.txt": "output_2"}}}}',
                        "io.simcore.thumbnail": '{"thumbnail": "https://www.statnews.com/wp-content/uploads/2020/05/3D-rat-heart.-iScience--768x432.png"}',
                        "io.simcore.type": '{"type": "computational"}',
                        "io.simcore.version": '{"version": "xxxxx"}'.replace(
                            "xxxxx", found["version"]
                        ),
                        "maintainer": "iavarone",
                        "org.label-schema.build-date": "2023-04-17T08:04:15Z",
                        "org.label-schema.schema-version": "1.0",
                        "org.label-schema.vcs-ref": "",
                        "org.label-schema.vcs-url": "",
                        "simcore.service.restart-policy": "no-restart",
                        "simcore.service.settings": '[{"name": "Resources", "type": "Resources", "value": {"Limits": {"NanoCPUs": 4000000000, "MemoryBytes": 2147483648}, "Reservations": {"NanoCPUs": 4000000000, "MemoryBytes": 2147483648}}}]',
                    }
                },
            )
        return httpx.Response(
            status.HTTP_404_NOT_FOUND,
            json={
                "data": {
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": f"The service {service_key}:{service_version}  does not exist",
                }
            },
        )

    # GET EXTRAS
    assert openapi["paths"].get("/service_extras/{service_key}/{service_version}")

    @respx_mock.get(
        path__regex=r"^/service_extras/(?P<service_key>[/\w-]+)/(?P<service_version>[0-9\.]+)$",
        name="get_service_extras",
    )
    def _get_service_extras(request, service_key, service_version):
        if _search(service_key, service_version):
            return httpx.Response(
                status.HTTP_200_OK,
                json={
                    "data": {
                        "node_requirements": {"CPU": 4, "RAM": 2147483648},
                        "build_date": "2023-04-17T08:04:15Z",
                        "vcs_ref": "",
                        "vcs_url": "",
                    }
                },
            )
        return httpx.Response(
            status.HTTP_404_NOT_FOUND,
            json={
                "data": {
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": f"The service {service_key}:{service_version}  does not exist",
                }
            },
        )

    return respx_mock
