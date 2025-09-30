# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=broad-exception-caught

import json
import re
import subprocess
from collections.abc import AsyncIterator, Callable, Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from urllib.parse import urlparse, urlunparse

import aiohttp.test_utils
import httpx
import pytest
import respx
import yaml
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from httpx import ASGITransport, Request, Response
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskProgress,
    TaskStatus,
)
from models_library.api_schemas_storage.storage_schemas import (
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompleteState,
    FileUploadSchema,
    HealthCheck,
)
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.app_diagnostics import AppStatusCheck
from models_library.generics import Envelope
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import BaseFileLink, SimcoreS3FileID
from models_library.rpc.webserver.projects import ProjectJobRpcGet
from models_library.users import UserID
from moto.server import ThreadedMotoServer
from packaging.version import Version
from pydantic import EmailStr, HttpUrl, TypeAdapter
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.catalog_rpc_server import CatalogRpcSideEffects
from pytest_simcore.helpers.director_v2_rpc_server import DirectorV2SideEffects
from pytest_simcore.helpers.host import get_localhost_ip
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.storage_rpc_server import StorageSideEffects
from pytest_simcore.helpers.webserver_rpc_server import WebserverRpcSideEffects
from pytest_simcore.simcore_webserver_projects_rest_api import GET_PROJECT
from requests.auth import HTTPBasicAuth
from respx import MockRouter
from simcore_service_api_server.api.dependencies.authentication import Identity
from simcore_service_api_server.core.application import create_app
from simcore_service_api_server.core.settings import ApplicationSettings
from simcore_service_api_server.models.api_resources import JobLinks
from simcore_service_api_server.repository.api_keys import UserAndProductTuple
from simcore_service_api_server.services_http.solver_job_outputs import ResultsTypes
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient


@pytest.fixture
def product_name() -> ProductName:
    return "osparc"


@pytest.fixture
def user_identity(
    user_id: UserID,
    user_email: EmailStr,
    product_name: ProductName,
) -> Identity:
    return Identity(
        user_id=user_id,
        product_name=product_name,
        email=user_email,
    )


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
        import simcore_service_api_server.core.application

        mocker.patch.object(
            simcore_service_api_server.core.application,
            "setup_rabbitmq",
            autospec=True,
        )
        mocker.patch.object(
            simcore_service_api_server.core.application,
            "setup_prometheus_instrumentation",
            autospec=True,
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

    return create_app()


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
    async with (
        LifespanManager(
            app,
            startup_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_STARTUP,
            shutdown_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_SHUTDOWN,
        ),
        httpx.AsyncClient(
            base_url="http://api.testserver.io",
            headers={"Content-Type": "application/json"},
            transport=ASGITransport(app=app),
        ) as httpx_async_client,
    ):
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
        engine.minsize = 2
        engine.size = 10
        engine.freesize = 3
        engine.maxsize = 10
        app.state.engine = engine
        async_engine = mocker.MagicMock()
        app.state.asyncpg_engine = async_engine

    # NOTE: here, instead of using the database, we patch repositories interface
    mocker.patch(
        "simcore_service_api_server.repository.api_keys.ApiKeysRepository.get_user",
        autospec=True,
        return_value=UserAndProductTuple(user_id=user_id, product_name="osparc"),
    )
    mocker.patch(
        "simcore_service_api_server.repository.users.UsersRepository.get_active_user_email",
        autospec=True,
        return_value=user_email,
    )

    return HTTPBasicAuth(user_api_key, user_api_secret)


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


## MOCKED res/web APIs from simcore services ------------------------------------------


@pytest.fixture
def mocked_app_dependencies(app: FastAPI, mocker: MockerFixture) -> Iterator[None]:
    """
    Mocks some dependency overrides for the FastAPI app.
    """
    assert app.state.settings.API_SERVER_RABBITMQ is None
    from servicelib.rabbitmq import RabbitMQRPCClient
    from simcore_service_api_server.api.dependencies.rabbitmq import (
        get_rabbitmq_rpc_client,
    )
    from simcore_service_api_server.api.dependencies.webserver_rpc import (
        get_wb_api_rpc_client,
    )

    def _get_rabbitmq_rpc_client_override():
        return mocker.MagicMock()

    async def _get_wb_api_rpc_client_override():
        from servicelib.rabbitmq.rpc_interfaces.webserver.v1 import WebServerRpcClient
        from simcore_service_api_server.core.settings import WebServerSettings

        webserver_settings: WebServerSettings = app.state.settings.API_SERVER_WEBSERVER
        assert webserver_settings.WEBSERVER_RPC_NAMESPACE

        rabbitmq_rpc_client = mocker.MagicMock(spec=RabbitMQRPCClient)
        return WbApiRpcClient(
            _rpc_client=WebServerRpcClient(
                rabbitmq_rpc_client, webserver_settings.WEBSERVER_RPC_NAMESPACE
            ),
        )

    app.dependency_overrides[get_rabbitmq_rpc_client] = (
        _get_rabbitmq_rpc_client_override
    )
    app.dependency_overrides[get_wb_api_rpc_client] = _get_wb_api_rpc_client_override

    yield

    app.dependency_overrides.pop(get_wb_api_rpc_client, None)
    app.dependency_overrides.pop(get_rabbitmq_rpc_client, None)


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
    openapi_path = osparc_simcore_services_dir / "storage" / "openapi.json"
    return json.loads(openapi_path.read_text())


@pytest.fixture
def catalog_service_openapi_specs(osparc_simcore_services_dir: Path) -> dict[str, Any]:
    openapi_path = osparc_simcore_services_dir / "catalog" / "openapi.json"
    return json.loads(openapi_path.read_text())


@pytest.fixture
def mocked_directorv2_rest_api_base(
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
def mocked_webserver_rest_api_base(
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
def mocked_storage_rest_api_base(
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
        assert openapi["paths"]["/v0/"]["get"]["operationId"] == "get_health_v0__get"

        respx_mock.get(path="/v0/", name="get_health_v0__get").respond(
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

        assert (
            openapi["paths"]["/v0/status"]["get"]["operationId"]
            == "get_status_v0_status_get"
        )
        respx_mock.get(path="/v0/status", name="get_status_v0_status_get").respond(
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

        assert (
            openapi["paths"]["/v0/locations/{location_id}/files/{file_id}"]["put"][
                "operationId"
            ]
            == "upload_file_v0_locations__location_id__files__file_id__put"
        )
        respx_mock.put(
            re.compile(r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files.+$"),
            name="upload_file_v0_locations__location_id__files__file_id__put",
        ).respond(
            status.HTTP_200_OK,
            json=Envelope[FileUploadSchema](
                data=FileUploadSchema.model_json_schema()["examples"][0]
            ).model_dump(mode="json"),
        )

        # Add mocks for completion and abort endpoints
        def generate_future_link(request: Request, **kwargs):
            parsed_url = urlparse(f"{request.url}")
            stripped_url = urlunparse(
                (parsed_url.scheme, parsed_url.netloc, parsed_url.path, "", "", "")
            )

            payload = FileUploadCompleteResponse.model_validate(
                {
                    "links": {
                        "state": stripped_url
                        + ":complete/futures/"
                        + str(faker.uuid4())
                    },
                },
            )
            return Response(
                status_code=status.HTTP_200_OK,
                json=jsonable_encoder(
                    Envelope[FileUploadCompleteResponse](data=payload)
                ),
            )

        respx_mock.post(
            re.compile(
                r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files/.+complete(?:\?.*)?$"
            ),
            name="complete_upload_file_v0_locations__location_id__files__file_id__complete_post",
        ).side_effect = generate_future_link

        respx_mock.post(
            re.compile(
                r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files/.+complete/futures/.+"
            )
        ).respond(
            status_code=status.HTTP_200_OK,
            json=jsonable_encoder(
                Envelope[FileUploadCompleteFutureResponse](
                    data=FileUploadCompleteFutureResponse(
                        state=FileUploadCompleteState.OK,
                        e_tag="07d1c1a4-b073-4be7-b022-f405d90e99aa",
                    )
                )
            ),
        )

        respx_mock.post(
            re.compile(
                r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files/.+:abort(?:\?.*)?$"
            ),
            name="abort_upload_file_v0_locations__location_id__files__file_id__abort_post",
        ).respond(
            status.HTTP_204_NO_CONTENT,
        )

        # SEE https://github.com/pcrespov/sandbox-python/blob/f650aad57aced304aac9d0ad56c00723d2274ad0/respx-lib/test_disable_mock.py
        if not services_mocks_enabled:
            respx_mock.stop()

        yield respx_mock


@pytest.fixture
def mocked_catalog_rest_api_base(
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
def project_job_rpc_get() -> ProjectJobRpcGet:
    example = ProjectJobRpcGet.model_json_schema()["examples"][0]
    return ProjectJobRpcGet.model_validate(example)


@pytest.fixture
def job_links() -> JobLinks:
    example = JobLinks.model_json_schema()["examples"][0]
    return JobLinks.model_validate(example)


@pytest.fixture
def mocked_webserver_rpc_api(
    mocked_app_dependencies: None,
    mocker: MockerFixture,
    project_job_rpc_get: ProjectJobRpcGet,
) -> dict[str, MockType]:
    """
    Mocks the webserver's simcore service RPC API for testing purposes.
    """
    from servicelib.rabbitmq.rpc_interfaces.webserver import (
        projects as projects_rpc,  # keep import here
    )

    side_effects = WebserverRpcSideEffects(project_job_rpc_get=project_job_rpc_get)

    return {
        "mark_project_as_job": mocker.patch.object(
            projects_rpc,
            "mark_project_as_job",
            autospec=True,
            side_effect=side_effects.mark_project_as_job,
        ),
        "get_project_marked_as_job": mocker.patch.object(
            projects_rpc,
            "get_project_marked_as_job",
            autospec=True,
            side_effect=side_effects.get_project_marked_as_job,
        ),
        "list_projects_marked_as_jobs": mocker.patch.object(
            projects_rpc,
            "list_projects_marked_as_jobs",
            autospec=True,
            side_effect=side_effects.list_projects_marked_as_jobs,
        ),
    }


@pytest.fixture
def catalog_rpc_side_effects(request) -> Any:
    if "param" in dir(request) and request.param is not None:
        return request.param
    return CatalogRpcSideEffects()


@pytest.fixture
def mocked_catalog_rpc_api(
    mocked_app_dependencies: None, mocker: MockerFixture, catalog_rpc_side_effects: Any
) -> dict[str, MockType]:
    """
    Mocks the catalog's simcore service RPC API for testing purposes.
    """
    from servicelib.rabbitmq.rpc_interfaces.catalog import (
        services as catalog_rpc,  # keep import here
    )

    mocks = {}

    # Get all callable methods from the side effects class that are not built-ins
    side_effect_methods = [
        method_name
        for method_name in dir(catalog_rpc_side_effects)
        if not method_name.startswith("_")
        and callable(getattr(catalog_rpc_side_effects, method_name))
    ]

    # Create mocks for each method in catalog_rpc that has a corresponding side effect
    for method_name in side_effect_methods:
        if hasattr(catalog_rpc, method_name):
            mocks[method_name] = mocker.patch.object(
                catalog_rpc,
                method_name,
                autospec=True,
                side_effect=getattr(catalog_rpc_side_effects, method_name),
            )

    return mocks


@pytest.fixture
def directorv2_rpc_side_effects(request) -> Any:
    if "param" in dir(request) and request.param is not None:
        return request.param
    return DirectorV2SideEffects()


@pytest.fixture
def mocked_directorv2_rpc_api(
    mocked_app_dependencies: None,
    mocker: MockerFixture,
    directorv2_rpc_side_effects: Any,
) -> dict[str, MockType]:
    """
    Mocks the director-v2's simcore service RPC API for testing purposes.
    """
    from servicelib.rabbitmq.rpc_interfaces.director_v2 import (
        computations_tasks as directorv2_rpc,  # keep import here
    )

    mocks = {}

    # Get all callable methods from the side effects class that are not built-ins
    side_effect_methods = [
        method_name
        for method_name in dir(directorv2_rpc_side_effects)
        if not method_name.startswith("_")
        and callable(getattr(directorv2_rpc_side_effects, method_name))
    ]

    # Create mocks for each method in directorv2_rpc that has a corresponding side effect
    for method_name in side_effect_methods:
        if hasattr(directorv2_rpc, method_name):
            mocks[method_name] = mocker.patch.object(
                directorv2_rpc,
                method_name,
                autospec=True,
                side_effect=getattr(directorv2_rpc_side_effects, method_name),
            )

    return mocks


@pytest.fixture
def storage_rpc_side_effects(request) -> Any:
    if "param" in dir(request) and request.param is not None:
        return request.param
    return StorageSideEffects()


@pytest.fixture
def mocked_storage_rpc_api(
    mocked_app_dependencies: None,
    mocker: MockerFixture,
    storage_rpc_side_effects: Any,
) -> dict[str, MockType]:
    """
    Mocks the storage's simcore service RPC API for testing purposes.
    """
    from servicelib.rabbitmq.rpc_interfaces.storage import (
        simcore_s3 as storage_rpc,  # keep import here
    )

    mocks = {}

    # Get all callable methods from the side effects class that are not built-ins
    side_effect_methods = [
        method_name
        for method_name in dir(storage_rpc_side_effects)
        if not method_name.startswith("_")
        and callable(getattr(storage_rpc_side_effects, method_name))
    ]

    # Create mocks for each method in storage_rpc that has a corresponding side effect
    for method_name in side_effect_methods:
        if hasattr(storage_rpc, method_name):
            mocks[method_name] = mocker.patch.object(
                storage_rpc,
                method_name,
                autospec=True,
                side_effect=getattr(storage_rpc_side_effects, method_name),
            )

    return mocks


#
# Other Mocks
#


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
        "simcore_service_api_server._service_jobs.get_solver_output_results",
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
            "simcore_service_api_server.services_http.webserver._get_lrt_urls",
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
                    "type": "STANDARD",
                    "templateType": None,
                    "dev": None,
                    "trashed_at": None,
                    "trashed_by": None,
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
            assert request
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
def mock_webserver_patch_project(
    app: FastAPI, services_mocks_enabled: bool
) -> Callable[[MockRouter], MockRouter]:
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER is not None

    def _mock(webserver_mock_router: MockRouter) -> MockRouter:
        def _patch_project(request: httpx.Request, *args, **kwargs):
            return httpx.Response(status.HTTP_200_OK)

        if services_mocks_enabled:
            webserver_mock_router.patch(
                path__regex=r"/projects/(?P<project_id>[\w-]+)$",
                name="project_patch",
            ).mock(side_effect=_patch_project)
        return webserver_mock_router

    return _mock


@pytest.fixture
def mock_webserver_get_project(
    app: FastAPI, services_mocks_enabled: bool
) -> Callable[[MockRouter], MockRouter]:
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER is not None

    def _mock(webserver_mock_router: MockRouter) -> MockRouter:
        def _get_project(request: httpx.Request, *args, **kwargs):
            result = Envelope[ProjectGet].model_validate(
                {"data": ProjectGet.model_json_schema()["examples"][0]}
            )
            return httpx.Response(status.HTTP_200_OK, json=result.model_dump())

        if services_mocks_enabled:
            webserver_mock_router.get(
                path__regex=r"/projects/(?P<project_id>[\w-]+)$",
                name="project_get",
            ).mock(side_effect=_get_project)
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
