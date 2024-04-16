# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import os
import subprocess
from collections.abc import AsyncIterator, Callable, Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any, TypeAlias
from unittest import mock

import aiohttp.test_utils
import httpx
import pytest
import respx
import yaml
from asgi_lifespan import LifespanManager
from cryptography.fernet import Fernet
from faker import Faker
from fastapi import FastAPI, status
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
from models_library.utils.fastapi_encoders import jsonable_encoder
from moto.server import ThreadedMotoServer
from packaging.version import Version
from pydantic import HttpUrl, parse_obj_as
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_host import get_localhost_ip
from pytest_simcore.simcore_webserver_projects_rest_api import GET_PROJECT
from requests.auth import HTTPBasicAuth
from respx import MockRouter
from simcore_service_api_server.core.application import init_app
from simcore_service_api_server.core.settings import ApplicationSettings
from simcore_service_api_server.db.repositories.api_keys import UserAndProductTuple
from simcore_service_api_server.services.solver_job_outputs import ResultsTypes
from simcore_service_api_server.utils.http_calls_capture import HttpApiCallCaptureModel
from simcore_service_api_server.utils.http_calls_capture_processing import (
    PathDescription,
)

# (capture.response_body, kwargs, capture.path.path_parameters) -> response_body
SideEffectCallback: TypeAlias = Callable[
    [httpx.Request, dict[str, Any], HttpApiCallCaptureModel], dict[str, Any]
]

## APP + SYNC/ASYNC CLIENTS --------------------------------------------------


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    default_app_env_vars: EnvVarsDict,
) -> EnvVarsDict:
    """Config that disables many plugins e.g. database or tracing"""
    env_vars = setenvs_from_dict(
        monkeypatch,
        {
            **default_app_env_vars,
            "WEBSERVER_HOST": "webserver",
            "WEBSERVER_SESSION_SECRET_KEY": Fernet.generate_key().decode("utf-8"),
            "API_SERVER_POSTGRES": "null",
            "API_SERVER_RABBITMQ": "null",
            "LOG_LEVEL": "debug",
            "SC_BOOT_MODE": "production",
            "API_SERVER_HEALTH_CHECK_TASK_PERIOD_SECONDS": "3",
            "API_SERVER_HEALTH_CHECK_TASK_TIMEOUT_SECONDS": "1",
        },
    )

    # should be sufficient to create settings
    print(ApplicationSettings.create_from_envs().json(indent=1))

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
def app(mock_missing_plugins: EnvVarsDict) -> FastAPI:
    """Inits app on a light environment"""
    return init_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    #
    # Prefer this client instead of fastapi.testclient.TestClient
    #

    # LifespanManager will trigger app's startup&shutown event handlers
    async with LifespanManager(app, shutdown_timeout=60), httpx.AsyncClient(
        base_url="http://api.testserver.io",
        headers={"Content-Type": "application/json"},
        transport=ASGITransport(app=app),
    ) as httpx_async_client:
        yield httpx_async_client


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

    # NOTE: here, instead of using the database, we patch repositories interface
    mocker.patch(
        "simcore_service_api_server.db.repositories.api_keys.ApiKeysRepository.get_user",
        autospec=True,
        return_value=UserAndProductTuple(user_id=faker.pyint(), product_name="osparc"),
    )
    mocker.patch(
        "simcore_service_api_server.db.repositories.users.UsersRepository.get_active_user_email",
        autospec=True,
        return_value=faker.email(),
    )

    return HTTPBasicAuth(faker.word(), faker.password())


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
        base_url=settings.API_SERVER_WEBSERVER.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
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
            query = dict(
                elm.split("=") for elm in request.url.query.decode().split("&")
            )
            if from_study := query.get("from_study"):
                return self.clone_project_task(request=request, project_id=from_study)
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
@respx.mock(assert_all_mocked=False)
def respx_mock_from_capture() -> (
    Callable[
        [list[respx.MockRouter], Path, list[SideEffectCallback]], list[respx.MockRouter]
    ]
):
    def _generate_mock(
        respx_mock: list[respx.MockRouter],
        capture_path: Path,
        side_effects_callbacks: list[SideEffectCallback],
    ) -> list[respx.MockRouter]:
        assert capture_path.is_file()
        assert capture_path.suffix == ".json"
        captures: list[HttpApiCallCaptureModel] = parse_obj_as(
            list[HttpApiCallCaptureModel], json.loads(capture_path.read_text())
        )

        if len(side_effects_callbacks) > 0:
            assert len(side_effects_callbacks) == len(captures)
        assert isinstance(respx_mock, list)
        for router in respx_mock:
            assert (
                router._bases
            ), "the base_url must be set before the fixture is extended"

        def _get_correct_mock_router_for_capture(
            respx_mock: list[respx.MockRouter], capture: HttpApiCallCaptureModel
        ) -> respx.MockRouter:
            for router in respx_mock:
                if capture.host == router._bases["host"].value:
                    return router
            msg = f"Missing respx.MockRouter for capture with {capture.host}"
            raise RuntimeError(msg)

        class CaptureSideEffect:
            def __init__(
                self,
                capture: HttpApiCallCaptureModel,
                side_effect: SideEffectCallback | None,
            ):
                self._capture = capture
                self._side_effect_callback = side_effect

            def _side_effect(self, request: httpx.Request, **kwargs):
                capture = self._capture
                assert isinstance(capture.path, PathDescription)
                status_code: int = capture.status_code
                response_body: dict[str, Any] | list | None = capture.response_body
                assert {param.name for param in capture.path.path_parameters} == set(
                    kwargs.keys()
                )
                if self._side_effect_callback:
                    response_body = self._side_effect_callback(request, kwargs, capture)
                return httpx.Response(status_code=status_code, json=response_body)

        side_effects: list[CaptureSideEffect] = []
        for ii, capture in enumerate(captures):
            url_path: PathDescription | str = capture.path
            assert isinstance(url_path, PathDescription)
            path_regex: str = str(url_path.path)
            side_effects.append(
                CaptureSideEffect(
                    capture=capture,
                    side_effect=side_effects_callbacks[ii]
                    if len(side_effects_callbacks)
                    else None,
                )
            )
            for param in url_path.path_parameters:
                path_regex = path_regex.replace(
                    "{" + param.name + "}", param.respx_lookup
                )
            router = _get_correct_mock_router_for_capture(respx_mock, capture)
            router.request(
                capture.method.upper(), url=None, path__regex="^" + path_regex + "$"
            ).mock(side_effect=side_effects[-1]._side_effect)

        return respx_mock

    return _generate_mock


@pytest.fixture
def openapi_dev_specs(project_slug_dir: Path) -> dict[str, Any]:
    openapi_file = (project_slug_dir / "openapi-dev.json").resolve()
    if openapi_file.is_file():
        os.remove(openapi_file)
    subprocess.run(
        "make openapi-dev.json", cwd=project_slug_dir, shell=True, check=True
    )
    assert openapi_file.is_file()
    return json.loads(openapi_file.read_text())
