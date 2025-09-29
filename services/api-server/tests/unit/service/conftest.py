# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

import pytest
from models_library.api_schemas_catalog import CATALOG_RPC_NAMESPACE
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.projects import ProjectCreateNew, ProjectGet
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from models_library.users import UserID
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.catalog_rpc_server import CatalogRpcSideEffects
from pytest_simcore.helpers.webserver_rpc_server import WebserverRpcSideEffects
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from simcore_service_api_server._service_jobs import JobService
from simcore_service_api_server._service_programs import ProgramService
from simcore_service_api_server._service_solvers import SolverService
from simcore_service_api_server.services_http.director_v2 import DirectorV2Api
from simcore_service_api_server.services_http.storage import StorageApi
from simcore_service_api_server.services_http.webserver import AuthSession
from simcore_service_api_server.services_rpc.catalog import CatalogService
from simcore_service_api_server.services_rpc.director_v2 import DirectorV2Service
from simcore_service_api_server.services_rpc.storage import StorageService
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient
from sqlalchemy.ext.asyncio import AsyncEngine


async def catalog_rpc_side_effect():
    return CatalogRpcSideEffects()


@pytest.fixture
def mocked_rpc_client(mocker: MockerFixture) -> MockType:
    """This fixture mocks the RabbitMQRPCClient.request method which is used
    in all RPC clients in the api-server, regardeless of the namespace.
    """

    async def _request(
        namespace: RPCNamespace,
        method_name: RPCMethodName,
        **kwargs,
    ) -> Any:

        kwargs.pop("timeout_s", None)  # remove timeout from kwargs

        # NOTE: we could switch to different namespaces
        if namespace == WEBSERVER_RPC_NAMESPACE:
            webserver_side_effect = WebserverRpcSideEffects()
            return await getattr(webserver_side_effect, method_name)(
                mocker.MagicMock(), **kwargs
            )

        if namespace == CATALOG_RPC_NAMESPACE:
            catalog_side_effect = CatalogRpcSideEffects()
            return await getattr(catalog_side_effect, method_name)(
                mocker.MagicMock(), **kwargs
            )

        pytest.fail(f"Unexpected namespace {namespace} and method {method_name}")

    mock = mocker.MagicMock(spec=RabbitMQRPCClient)
    mock.request.side_effect = _request

    return mock


@pytest.fixture
def wb_api_rpc_client(
    mocked_rpc_client: MockType,
    mocker: MockerFixture,
) -> WbApiRpcClient:
    from servicelib.rabbitmq.rpc_interfaces.webserver.v1 import WebServerRpcClient

    return WbApiRpcClient(
        _client=mocked_rpc_client, _rpc_client=mocker.MagicMock(spec=WebServerRpcClient)
    )


@pytest.fixture
def director_v2_rpc_client(
    mocked_rpc_client: MockType,
) -> DirectorV2Service:
    return DirectorV2Service(_rpc_client=mocked_rpc_client)


@pytest.fixture
def storage_rpc_client(
    mocked_rpc_client: MockType,
    user_id: UserID,
    product_name: ProductName,
) -> StorageService:
    return StorageService(
        _rpc_client=mocked_rpc_client, _user_id=user_id, _product_name=product_name
    )


@pytest.fixture
def auth_session(
    mocker: MockerFixture,
    # mocked_webserver_rest_api_base: MockRouter, app: FastAPI
) -> AuthSession:
    # return AuthSession.create(app, session_cookies={}, product_extra_headers={})
    mock = mocker.AsyncMock(spec=AuthSession)

    async def _create_project(project: ProjectCreateNew, **kwargs):
        example = ProjectGet.model_json_schema()["examples"][0]
        example.update(project.model_dump(exclude_unset=True))
        return ProjectGet.model_validate(example)

    mock.create_project.side_effect = _create_project
    return mock


@pytest.fixture
def director2_api(mocker: MockerFixture) -> DirectorV2Api:
    return mocker.AsyncMock(spec=DirectorV2Api)


@pytest.fixture
def storage_rest_client(
    mocker: MockerFixture,
) -> StorageApi:
    return mocker.AsyncMock(spec=StorageApi)


@pytest.fixture
def catalog_service(
    mocked_rpc_client: MockType,
    product_name: ProductName,
    user_id: UserID,
) -> CatalogService:
    return CatalogService(
        _rpc_client=mocked_rpc_client, user_id=user_id, product_name=product_name
    )


@pytest.fixture
def solver_service(
    catalog_service: CatalogService,
    product_name: ProductName,
    user_id: UserID,
) -> SolverService:
    return SolverService(
        catalog_service=catalog_service,
        user_id=user_id,
        product_name=product_name,
    )


@pytest.fixture
def program_service(
    catalog_service: CatalogService,
) -> ProgramService:
    return ProgramService(catalog_service=catalog_service)


@pytest.fixture
def async_pg_engine(mocker: MockerFixture) -> AsyncEngine:
    return mocker.MagicMock(spec=AsyncEngine)


@pytest.fixture
def job_service(
    auth_session: AuthSession,
    director_v2_rpc_client: DirectorV2Service,
    storage_rpc_client: StorageService,
    wb_api_rpc_client: WbApiRpcClient,
    director2_api: DirectorV2Api,
    storage_rest_client: StorageApi,
    product_name: ProductName,
    user_id: UserID,
    solver_service: SolverService,
    async_pg_engine: AsyncEngine,
) -> JobService:
    return JobService(
        _web_rest_client=auth_session,
        _web_rpc_client=wb_api_rpc_client,
        _storage_rpc_client=storage_rpc_client,
        _storage_rest_client=storage_rest_client,
        _directorv2_rpc_client=director_v2_rpc_client,
        _director2_api=director2_api,
        _solver_service=solver_service,
        user_id=user_id,
        product_name=product_name,
    )
