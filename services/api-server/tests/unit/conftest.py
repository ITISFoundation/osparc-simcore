# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from collections.abc import AsyncIterator, Callable, Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import aiohttp.test_utils
import httpx
import pytest
import respx
import yaml
from asgi_lifespan import LifespanManager
from cryptography.fernet import Fernet
from faker import Faker
from fastapi import FastAPI, status
from httpx._transports.asgi import ASGITransport
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskProgress,
    TaskStatus,
)
from models_library.api_schemas_storage import HealthCheck
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.app_diagnostics import AppStatusCheck
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.utils.fastapi_encoders import jsonable_encoder
from moto.server import ThreadedMotoServer
from packaging.version import Version
from pydantic import HttpUrl, parse_obj_as
from pytest import MonkeyPatch  # noqa: PT013
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.simcore_webserver_projects_rest_api import GET_PROJECT
from requests.auth import HTTPBasicAuth
from respx import MockRouter
from simcore_service_api_server.core.application import init_app
from simcore_service_api_server.core.settings import (
    ApplicationSettings,
    CatalogSettings,
    StorageSettings,
)
from simcore_service_api_server.utils.http_calls_capture import HttpApiCallCaptureModel
from simcore_service_api_server.utils.http_calls_capture_processing import (
    Param,
    UrlPath,
)

## APP + SYNC/ASYNC CLIENTS --------------------------------------------------


@pytest.fixture
def app_environment(
    monkeypatch: MonkeyPatch, default_app_env_vars: EnvVarsDict
) -> EnvVarsDict:
    """Config that disables many plugins e.g. database or tracing"""

    env_vars = setenvs_from_dict(
        monkeypatch,
        {
            **default_app_env_vars,
            "WEBSERVER_HOST": "webserver",
            "WEBSERVER_SESSION_SECRET_KEY": Fernet.generate_key().decode("utf-8"),
            "API_SERVER_POSTGRES": "null",
            "LOG_LEVEL": "debug",
            "SC_BOOT_MODE": "production",
        },
    )

    # should be sufficient to create settings
    print(ApplicationSettings.create_from_envs().json(indent=1))

    return env_vars


@pytest.fixture
def app(app_environment: EnvVarsDict) -> FastAPI:
    """Inits app on a light environment"""
    return init_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    #
    # Prefer this client instead of fastapi.testclient.TestClient
    #
    async with LifespanManager(app):
        # needed for app to trigger start/stop event handlers
        async with httpx.AsyncClient(
            app=app,
            base_url="http://api.testserver.io",
            headers={"Content-Type": "application/json"},
        ) as client:
            assert isinstance(client._transport, ASGITransport)
            # rewires location test's app to client.app
            client.app = client._transport.app

            yield client


## MOCKED Repositories --------------------------------------------------


@pytest.fixture
def auth(mocker, app: FastAPI, faker: Faker) -> HTTPBasicAuth:
    """
    Auth mocking repositories and db engine (i.e. does not require db up)

    """
    # mock engine if db was not init
    if app.state.settings.API_SERVER_POSTGRES is None:
        engine = mocker.MagicMock()
        engine.minsize = 1
        engine.size = 10
        engine.freesize = 3
        engine.maxsize = 10
        app.state.engine = engine

    # patch authentication entry in repo
    faker_user_id = faker.pyint()

    # NOTE: here, instead of using the database, we patch repositories interface
    mocker.patch(
        "simcore_service_api_server.db.repositories.api_keys.ApiKeysRepository.get_user_id",
        autospec=True,
        return_value=faker_user_id,
    )
    mocker.patch(
        "simcore_service_api_server.db.repositories.users.UsersRepository.get_user_id",
        autospec=True,
        return_value=faker_user_id,
    )
    mocker.patch(
        "simcore_service_api_server.db.repositories.users.UsersRepository.get_email_from_user_id",
        autospec=True,
        return_value=faker.email(),
    )

    # patches simcore_postgres_database.utils_products.get_default_product_name
    mocker.patch(
        "simcore_service_api_server.api.dependencies.application.get_default_product_name",
        autospec=True,
        return_value="osparc",
    )

    return HTTPBasicAuth(faker.word(), faker.password())


## MOCKED S3 service --------------------------------------------------


@pytest.fixture
def mocked_s3_server_url() -> Iterator[HttpUrl]:
    """
    For download links, the in-memory moto.mock_s3() does not suffice since
    we need an http entrypoint
    """
    # http://docs.getmoto.org/en/latest/docs/server_mode.html#start-within-python
    server = ThreadedMotoServer(
        ip_address=get_localhost_ip(), port=aiohttp.test_utils.unused_port()
    )

    # pylint: disable=protected-access
    endpoint_url = parse_obj_as(HttpUrl, f"http://{server._ip_address}:{server._port}")

    print(f"--> started mock S3 server on {endpoint_url}")
    server.start()

    yield endpoint_url

    server.stop()
    print(f"<-- stopped mock S3 server on {endpoint_url}")


## MOCKED stack services --------------------------------------------------


@pytest.fixture
def directorv2_service_openapi_specs(
    osparc_simcore_services_dir: Path,
) -> dict[str, Any]:
    openapi_path = osparc_simcore_services_dir / "director-v2" / "openapi.json"
    return json.loads(openapi_path.read_text())


@pytest.fixture
def webserver_service_openapi_specs(
    osparc_simcore_services_dir: Path,
) -> dict[str, Any]:
    openapi_path = (
        osparc_simcore_services_dir
        / "web/server/src/simcore_service_webserver/api/v0/openapi.yaml"
    )
    return yaml.safe_load(openapi_path.read_text())


@pytest.fixture
def storage_service_openapi_specs(
    osparc_simcore_services_dir: Path,
) -> dict[str, Any]:
    openapi_path = (
        osparc_simcore_services_dir
        / "storage/src/simcore_service_storage/api/v0/openapi.yaml"
    )
    return yaml.safe_load(openapi_path.read_text())


@pytest.fixture
def catalog_service_openapi_specs(osparc_simcore_services_dir: Path) -> dict[str, Any]:
    openapi_path = osparc_simcore_services_dir / "catalog" / "openapi.json"
    return json.loads(openapi_path.read_text())


@pytest.fixture
def mocked_directorv2_service_api_base(
    app: FastAPI,
    directorv2_service_openapi_specs: dict[str, Any],
) -> Iterator[MockRouter]:
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_DIRECTOR_V2

    openapi = deepcopy(directorv2_service_openapi_specs)
    assert Version(openapi["info"]["version"]).major == 2

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_DIRECTOR_V2.base_url,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as respx_mock:
        assert openapi
        assert (
            openapi["paths"]["/"]["get"]["operationId"] == "check_service_health__get"
        )

        respx_mock.get(path="/", name="check_service_health__get").respond(
            status.HTTP_200_OK,
            json=openapi["components"]["schemas"]["HealthCheckGet"]["example"],
        )

        yield respx_mock


@pytest.fixture
def mocked_webserver_service_api_base(
    app: FastAPI, webserver_service_openapi_specs: dict[str, Any]
) -> Iterator[MockRouter]:
    """
    Creates a respx.mock to capture calls to webserver API
    Includes only basic routes to check that the configuration is correct
    IMPORTANT: This fixture shall be extended on a test bases
    """
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER

    openapi = deepcopy(webserver_service_openapi_specs)
    assert Version(openapi["info"]["version"]).major == 0

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_WEBSERVER.api_base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # WARNING: For this service, DO NOT include /v0 in the `path` to match !!!!
        assert settings.API_SERVER_WEBSERVER.api_base_url.endswith("/v0")

        # healthcheck_readiness_probe, healthcheck_liveness_probe
        response_body = {
            "name": "webserver",
            "version": "1.0.0",
            "api_version": "1.0.0",
        }

        respx_mock.get(path="/", name="healthcheck_readiness_probe").respond(
            status.HTTP_200_OK, json=response_body
        )
        respx_mock.get(path="/health", name="healthcheck_liveness_probe").respond(
            status.HTTP_200_OK, json=response_body
        )

        yield respx_mock


@pytest.fixture
def mocked_storage_service_api_base(
    app: FastAPI, storage_service_openapi_specs: dict[str, Any], faker: Faker
) -> Iterator[MockRouter]:
    """
    Creates a respx.mock to capture calls to strage API
    Includes only basic routes to check that the configuration is correct
    IMPORTANT: This fixture shall be extended on a test bases
    """
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_STORAGE

    openapi = deepcopy(storage_service_openapi_specs)
    assert Version(openapi["info"]["version"]).major == 0

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_STORAGE.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        assert openapi["paths"]["/v0/"]["get"]["operationId"] == "health_check"
        respx_mock.get(path="/v0/", name="health_check").respond(
            status.HTTP_200_OK,
            json=Envelope[HealthCheck](
                data={
                    "name": "storage",
                    "status": "ok",
                    "api_version": "1.0.0",
                    "version": "1.0.0",
                },
            ).dict(),
        )

        assert openapi["paths"]["/v0/status"]["get"]["operationId"] == "get_status"
        respx_mock.get(path="/v0/status", name="get_status").respond(
            status.HTTP_200_OK,
            json=Envelope[AppStatusCheck](
                data={
                    "app_name": "storage",
                    "version": "1.0.0",
                    "url": faker.url(),
                    "diagnostics_url": faker.url(),
                }
            ).dict(),
        )

        yield respx_mock


@pytest.fixture
def mocked_catalog_service_api_base(
    app: FastAPI, catalog_service_openapi_specs: dict[str, Any]
) -> Iterator[MockRouter]:
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_CATALOG

    openapi = deepcopy(catalog_service_openapi_specs)
    assert Version(openapi["info"]["version"]).major == 0
    schemas = openapi["components"]["schemas"]

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_CATALOG.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.get("/v0/").respond(
            status.HTTP_200_OK,
            text="simcore_service_catalog.api.routes.health@2023-07-03T12:59:12.024551+00:00",
        )
        respx_mock.get("/v0/meta").respond(
            status.HTTP_200_OK, json=schemas["Meta"]["example"]
        )

        yield respx_mock


@pytest.fixture
def patch_webserver_long_running_project_tasks(
    app: FastAPI, faker: Faker
) -> Callable[[MockRouter], MockRouter]:
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER is not None

    class _LongRunningProjectTasks:
        """
        Preserves results per task_id
        """

        def __init__(self):
            self._results: dict[str, Any] = {}

        def _set_result_and_get_reponse(self, result: Any):
            task_id = faker.uuid4()
            self._results[task_id] = jsonable_encoder(result, by_alias=True)

            return httpx.Response(
                status.HTTP_202_ACCEPTED,
                json={
                    "data": TaskGet(
                        task_id=task_id,
                        task_name="fake-task-name",
                        status_href=f"{settings.API_SERVER_WEBSERVER.api_base_url}/tasks/{task_id}",
                        result_href=f"{settings.API_SERVER_WEBSERVER.api_base_url}/tasks/{task_id}/result",
                        abort_href=f"{settings.API_SERVER_WEBSERVER.api_base_url}/tasks/{task_id}",
                    ).dict()
                },
            )

        # SIDE EFFECT functions ---

        def create_project_task(self, request: httpx.Request):
            # create result: use the request-body
            project_create = json.loads(request.content)
            project_get = ProjectGet.parse_obj(
                {
                    "creationDate": "2018-07-01T11:13:43Z",
                    "lastChangeDate": "2018-07-01T11:13:43Z",
                    "prjOwner": "owner@email.com",
                    **project_create,
                }
            )

            return self._set_result_and_get_reponse(project_get)

        def clone_project_task(self, request: httpx.Request, *, project_id: str):
            assert GET_PROJECT.response_body

            project_get = ProjectGet.parse_obj(
                {
                    "creationDate": "2018-07-01T11:13:43Z",
                    "lastChangeDate": "2018-07-01T11:13:43Z",
                    "prjOwner": "owner@email.com",
                    **GET_PROJECT.response_body["data"],
                }
            )
            project_get.uuid = ProjectID(project_id)

            return self._set_result_and_get_reponse(project_get)

        def get_result(self, request: httpx.Request, *, task_id: str):
            return httpx.Response(
                status.HTTP_200_OK, json={"data": self._results[task_id]}
            )

        # NOTE: Due to lack of time, i will leave it here but I believe
        # it is possible to have a generic long-running task workflow
        # that preserves the resultswith state

    def _mock(webserver_mock_router: MockRouter) -> MockRouter:
        long_running_task_workflow = _LongRunningProjectTasks()

        webserver_mock_router.post(
            path__regex="/projects$",
            name="create_projects",
        ).mock(side_effect=long_running_task_workflow.create_project_task)

        webserver_mock_router.post(
            path__regex=r"/projects/(?P<project_id>[\w-]+):clone$",
            name="project_clone",
        ).mock(side_effect=long_running_task_workflow.clone_project_task)

        # Tasks routes ----------------

        webserver_mock_router.get(
            path__regex=r"/tasks/(?P<task_id>[\w-]+)$",
            name="get_task_status",
        ).respond(
            status.HTTP_200_OK,
            json={
                "data": jsonable_encoder(
                    TaskStatus(
                        task_progress=TaskProgress(message="fake job done", percent=1),
                        done=True,
                        started="2018-07-01T11:13:43Z",
                    ),
                    by_alias=True,
                )
            },
        )

        webserver_mock_router.get(
            path__regex=r"/tasks/(?P<task_id>[\w-]+)/result$",
            name="get_task_result",
        ).mock(side_effect=long_running_task_workflow.get_result)

        return webserver_mock_router

    return _mock


@pytest.fixture
def respx_mock_from_capture() -> Callable[[Path], list[respx.Route]]:
    def _generate_mock(capture_path: Path) -> list[respx.Route]:
        assert capture_path.is_file() and capture_path.suffix == ".json"
        captures: list[HttpApiCallCaptureModel] = parse_obj_as(
            list[HttpApiCallCaptureModel], json.loads(capture_path.read_text())
        )

        routes: list[respx.Route] = []

        for capture in captures:
            status_code: int = capture.status_code
            path_params: set[Param] = capture.path.path_parameters
            response_body: str = json.dumps(capture.response_body)

            def _side_effect(request: httpx.Request, **kwargs):
                for param in path_params:
                    assert param.response_value is not None
                    response_body.replace(param.response_value, kwargs[param.name])
                return httpx.Response(
                    status_code=status_code, json=json.loads(response_body)
                )

            url_path: UrlPath = capture.path
            path: str = str(url_path.path)
            for param in url_path.path_parameters:
                path = path.replace("{" + param.name + "}", param.regex_lookup)

            _base_url: str = ""
            if capture.host == "storage":
                _base_url = StorageSettings().base_url
            elif capture.host == "catalog":
                _base_url = CatalogSettings().base_url

            assert (
                _base_url != ""
            ), f"{capture.host} hasn't been configured yet. Please add it"

            routes.append(
                respx.route(
                    method=capture.method, base_url=_base_url, path__regex=path
                ).mock(side_effect=_side_effect)
            )

        return routes

    return _generate_mock
