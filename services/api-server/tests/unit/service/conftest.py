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
from simcore_service_api_server._service_studies import StudyService
from simcore_service_api_server.services_http.webserver import AuthSession
from simcore_service_api_server.services_rpc.catalog import CatalogService
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient


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
) -> WbApiRpcClient:
    return WbApiRpcClient(_client=mocked_rpc_client)


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
def job_service(
    auth_session: AuthSession,
    wb_api_rpc_client: WbApiRpcClient,
    product_name: ProductName,
    user_id: UserID,
) -> JobService:
    return JobService(
        _web_rest_client=auth_session,
        _web_rpc_client=wb_api_rpc_client,
        user_id=user_id,
        product_name=product_name,
    )


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
    job_service: JobService,
    product_name: ProductName,
    user_id: UserID,
) -> SolverService:
    return SolverService(
        catalog_service=catalog_service,
        job_service=job_service,
        user_id=user_id,
        product_name=product_name,
    )


@pytest.fixture
def study_service(
    job_service: JobService,
    auth_session: AuthSession,
    wb_api_rpc_client: WbApiRpcClient,
    product_name: ProductName,
    user_id: UserID,
) -> StudyService:

    return StudyService(
        job_service=job_service,
        webserver_api=auth_session,
        wb_api_rpc=wb_api_rpc_client,
        user_id=user_id,
        product_name=product_name,
    )


@pytest.fixture
def program_service(
    catalog_service: CatalogService,
) -> ProgramService:
    return ProgramService(catalog_service=catalog_service)
