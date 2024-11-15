# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import subprocess
from collections.abc import AsyncIterator, Callable, Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import MagicMock

import aiohttp.test_utils
import httpx
import pytest
import respx
import yaml
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from httpx import ASGITransport
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
from models_library.projects_nodes_io import BaseFileLink, SimcoreS3FileID
from models_library.users import UserID
from moto.server import ThreadedMotoServer
from packaging.version import Version
from pydantic import EmailStr, HttpUrl, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.host import get_localhost_ip
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.simcore_webserver_projects_rest_api import GET_PROJECT
from requests.auth import HTTPBasicAuth
from respx import MockRouter
from simcore_service_api_server.core.application import init_app
from simcore_service_api_server.core.settings import ApplicationSettings
from simcore_service_api_server.db.repositories.api_keys import UserAndProductTuple
from simcore_service_api_server.services.solver_job_outputs import ResultsTypes


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    default_app_env_vars: EnvVarsDict,
    backend_env_vars_overrides: EnvVarsDict,
) -> EnvVarsDict:
    env_vars = setenvs_from_dict(
        monkeypatch,
        {
            **default_app_env_vars,
            "WEBSERVER_HOST": "webserver",
            "API_SERVER_POSTGRES": "null",
            "API_SERVER_RABBITMQ": "null",
            "API_SERVER_TRACING": "null",
            "LOG_LEVEL": "debug",
            "SC_BOOT_MODE": "production",
            "API_SERVER_HEALTH_CHECK_TASK_PERIOD_SECONDS": "3",
            "API_SERVER_HEALTH_CHECK_TASK_TIMEOUT_SECONDS": "1",
            "API_SERVER_LOG_CHECK_TIMEOUT_SECONDS": "1",
            **backend_env_vars_overrides,
        },
    )

    # should be sufficient to create settings
    print(ApplicationSettings.create_from_envs().model_dump_json(indent=1))

    return env_vars


@pytest.fixture
def mock_missing_plugins(app_environment: EnvVarsDict, mocker: MockerFixture):
    settings = ApplicationSettings.create_from_envs()
    if settings.API_SERVER_RABBITMQ is None:
        mocker.patch("simcore_service_api_server.core.application.setup_rabbitmq")
        mocker.patch(
            "simcore_service_api_server.core._prometheus_instrumentation.setup_prometheus_instrumentation"
        )
    return app_environment


@pytest.fixture
def app(
    mock_missing_plugins: EnvVarsDict,
    create_httpx_async_client_spy_if_enabled: Callable,
    patch_lrt_response_urls: Callable,
    spy_httpx_calls_enabled: bool,
) -> FastAPI:
    """Inits app on a light environment"""

    if spy_httpx_calls_enabled:
        create_httpx_async_client_spy_if_enabled(
            "simcore_service_api_server.utils.client_base.AsyncClient"
        )

        patch_lrt_response_urls()

    return init_app()


MAX_TIME_FOR_APP_TO_STARTUP = 10
MAX_TIME_FOR_APP_TO_SHUTDOWN = 10


@pytest.fixture
async def client(
    app: FastAPI, is_pdb_enabled: bool
) -> AsyncIterator[httpx.AsyncClient]:
    #
    # Prefer this client instead of fastapi.testclient.TestClient
    #

    # LifespanManager will trigger app's startup&shutown event handlers
    async with LifespanManager(
        app,
        startup_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_STARTUP,
        shutdown_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_SHUTDOWN,
    ), httpx.AsyncClient(
        base_url="http://api.testserver.io",
        headers={"Content-Type": "application/json"},
        transport=ASGITransport(app=app),
    ) as httpx_async_client:
        assert isinstance(httpx_async_client, httpx.AsyncClient)
        yield httpx_async_client


## MOCKED Repositories --------------------------------------------------


@pytest.fixture
def auth(
    mocker: MockerFixture,
    app: FastAPI,
    user_id: UserID,
    user_email: EmailStr,
    user_api_key: str,
    user_api_secret: str,
) -> HTTPBasicAuth:
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

    # NOTE: here, instead of using the database, we patch repositories interface
    mocker.patch(
        "simcore_service_api_server.db.repositories.api_keys.ApiKeysRepository.get_user",
        autospec=True,
        return_value=UserAndProductTuple(user_id=user_id, product_name="osparc"),
    )
    mocker.patch(
        "simcore_service_api_server.db.repositories.users.UsersRepository.get_active_user_email",
        autospec=True,
        return_value=user_email,
    )

    return HTTPBasicAuth(user_api_key, user_api_secret)


@pytest.fixture
def mocked_groups_extra_properties(mocker: MockerFixture) -> mock.Mock:
    from simcore_service_api_server.db.repositories.groups_extra_properties import (
        GroupsExtraPropertiesRepository,
    )

    return mocker.patch.object(
        GroupsExtraPropertiesRepository,
        "use_on_demand_clusters",
        autospec=True,
        return_value=True,
    )


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
    endpoint_url = TypeAdapter(HttpUrl).validate_python(
        f"http://{server._ip_address}:{server._port}"
    )

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
    services_mocks_enabled: bool,
) -> Iterator[MockRouter]:
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_DIRECTOR_V2

    openapi = deepcopy(directorv2_service_openapi_specs)
    assert Version(openapi["info"]["version"]).major == 2

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_DIRECTOR_V2.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        assert openapi
        assert (
            openapi["paths"]["/"]["get"]["operationId"] == "check_service_health__get"
        )

        respx_mock.get(path="/", name="check_service_health__get").respond(
            status.HTTP_200_OK,
            json=openapi["components"]["schemas"]["HealthCheckGet"]["example"],
        )

        # SEE https://github.com/pcrespov/sandbox-python/blob/f650aad57aced304aac9d0ad56c00723d2274ad0/respx-lib/test_disable_mock.py
        if not services_mocks_enabled:
            respx_mock.stop()

        yield respx_mock


@pytest.fixture
def mocked_webserver_service_api_base(
    app: FastAPI,
    webserver_service_openapi_specs: dict[str, Any],
    services_mocks_enabled: bool,
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
        base_url=settings.API_SERVER_WEBSERVER.base_url,
        assert_all_called=False,
    ) as respx_mock:
        # healthcheck_readiness_probe, healthcheck_liveness_probe
        response_body = {
            "name": "webserver",
            "version": "1.0.0",
            "api_version": "1.0.0",
        }
        respx_mock.get(path="/v0/", name="healthcheck_readiness_probe").respond(
            status.HTTP_200_OK, json=response_body
        )
        respx_mock.get(path="/v0/health", name="healthcheck_liveness_probe").respond(
            status.HTTP_200_OK, json=response_body
        )

        # SEE https://github.com/pcrespov/sandbox-python/blob/f650aad57aced304aac9d0ad56c00723d2274ad0/respx-lib/test_disable_mock.py
        if not services_mocks_enabled:
            respx_mock.stop()

        yield respx_mock


@pytest.fixture
def mocked_storage_service_api_base(
    app: FastAPI,
    storage_service_openapi_specs: dict[str, Any],
    faker: Faker,
    services_mocks_enabled: bool,
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
            ).model_dump(),
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
            ).model_dump(mode="json"),
        )

        # SEE https://github.com/pcrespov/sandbox-python/blob/f650aad57aced304aac9d0ad56c00723d2274ad0/respx-lib/test_disable_mock.py
        if not services_mocks_enabled:
            respx_mock.stop()

        yield respx_mock


@pytest.fixture
def mocked_catalog_service_api_base(
    app: FastAPI,
    catalog_service_openapi_specs: dict[str, Any],
    services_mocks_enabled: bool,
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
    ) as respx_mock:
        respx_mock.get("/v0/").respond(
            status.HTTP_200_OK,
            text="simcore_service_catalog.api.routes.health@2023-07-03T12:59:12.024551+00:00",
        )
        respx_mock.get("/v0/meta").respond(
            status.HTTP_200_OK, json=schemas["BaseMeta"]["example"]
        )

        # SEE https://github.com/pcrespov/sandbox-python/blob/f650aad57aced304aac9d0ad56c00723d2274ad0/respx-lib/test_disable_mock.py
        if not services_mocks_enabled:
            respx_mock.stop()

        yield respx_mock


@pytest.fixture
def mocked_solver_job_outputs(mocker) -> None:
    result: dict[str, ResultsTypes] = {}
    result["output_1"] = 0.6
    result["output_2"] = BaseFileLink(
        store=0,
        path=SimcoreS3FileID(
            "api/7cf771db-3ee9-319e-849f-53db0076fc93/single_number.txt"
        ),
        label=None,
        eTag=None,
    )
    mocker.patch(
        "simcore_service_api_server.api.routes.solvers_jobs_getters.get_solver_output_results",
        autospec=True,
        return_value=result,
    )


@pytest.fixture
def patch_lrt_response_urls(mocker: MockerFixture):
    """
    Callable that patches webserver._get_lrt_urls helper
    when running in spy mode
    """

    def _() -> MagicMock:
        def _get_lrt_urls(lrt_response: httpx.Response):
            # NOTE: this function is needed to mock
            data = Envelope[TaskGet].model_validate_json(lrt_response.text).data
            assert data is not None  # nosec

            def _patch(href):
                return lrt_response.request.url.copy_with(
                    raw_path=httpx.URL(href).raw_path
                )

            data.status_href = _patch(data.status_href)
            data.result_href = _patch(data.result_href)

            return data.status_href, data.result_href

        return mocker.patch(
            "simcore_service_api_server.services.webserver._get_lrt_urls",
            side_effect=_get_lrt_urls,
        )

    return _


@pytest.fixture
def patch_webserver_long_running_project_tasks(
    app: FastAPI, faker: Faker, services_mocks_enabled: bool
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
                    ).model_dump()
                },
            )

        # SIDE EFFECT functions ---

        def create_project_task(self, request: httpx.Request):
            # create result: use the request-body
            query = dict(
                elm.split("=") for elm in request.url.query.decode().split("&")
            )
            if from_study := query.get("from_study"):
                return self.clone_project_task(request=request, project_id=from_study)
            project_create = json.loads(request.content)
            project_get = ProjectGet.model_validate(
                {
                    "creationDate": "2018-07-01T11:13:43Z",
                    "lastChangeDate": "2018-07-01T11:13:43Z",
                    "prjOwner": "owner@email.com",
                    "dev": None,
                    "trashed_at": None,
                    **project_create,
                }
            )

            return self._set_result_and_get_reponse(project_get)

        def clone_project_task(self, request: httpx.Request, *, project_id: str):
            assert GET_PROJECT.response_body

            project_get = ProjectGet.model_validate(
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
        if services_mocks_enabled:
            long_running_task_workflow = _LongRunningProjectTasks()

            webserver_mock_router.post(
                path__regex="/projects",
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
                            task_progress=TaskProgress(
                                message="fake job done", percent=1
                            ),
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
def openapi_dev_specs(project_slug_dir: Path) -> dict[str, Any]:
    openapi_file = (project_slug_dir / "openapi-dev.json").resolve()
    if openapi_file.is_file():
        openapi_file.unlink()
    subprocess.run(
        "make openapi-dev.json", cwd=project_slug_dir, shell=True, check=True
    )
    assert openapi_file.is_file()
    return json.loads(openapi_file.read_text())
