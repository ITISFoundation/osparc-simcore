# pylint: disable=redefined-outer-name

import datetime
from uuid import uuid4

import pytest
from faker import Faker
from models_library.api_schemas_webserver.functions import (
    FunctionClass,
    JSONFunctionInputSchema,
    JSONFunctionOutputSchema,
    RegisteredProjectFunction,
)
from models_library.functions import RegisteredFunction
from models_library.products import ProductName
from models_library.users import UserID
from pytest_mock import MockerFixture
from simcore_service_api_server._service_function_jobs import FunctionJobService
from simcore_service_api_server._service_functions import FunctionService
from simcore_service_api_server._service_jobs import JobService
from simcore_service_api_server.services_http.webserver import AuthSession
from simcore_service_api_server.services_rpc.storage import StorageService
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient

_faker = Faker()


@pytest.fixture
def registered_project_function() -> RegisteredFunction:
    return RegisteredProjectFunction(
        title="test_function",
        function_class=FunctionClass.PROJECT,
        description="A test function",
        input_schema=JSONFunctionInputSchema(
            schema_content={
                "type": "object",
                "properties": {"input1": {"type": "integer"}},
            }
        ),
        output_schema=JSONFunctionOutputSchema(
            schema_content={
                "type": "object",
                "properties": {"output1": {"type": "string"}},
            }
        ),
        default_inputs=None,
        project_id=uuid4(),
        uid=uuid4(),
        created_at=datetime.datetime.now(datetime.UTC),
        modified_at=datetime.datetime.now(datetime.UTC),
    )


@pytest.fixture
def function_job_service(
    mocker: MockerFixture,
    user_id: UserID,
    product_name: ProductName,
) -> FunctionJobService:
    return FunctionJobService(
        user_id=user_id,
        product_name=product_name,
        _web_rpc_client=mocker.AsyncMock(spec=WbApiRpcClient),
        _storage_client=mocker.AsyncMock(spec=StorageService),
        _job_service=mocker.AsyncMock(spec=JobService),
        _function_service=mocker.AsyncMock(spec=FunctionService),
        _webserver_api=mocker.AsyncMock(spec=AuthSession),
    )


async def test_batch_pre_register_function_jobs_with_empty_list(
    function_job_service: FunctionJobService,
    registered_project_function: RegisteredFunction,
):
    result = await function_job_service.batch_pre_register_function_jobs(
        function=registered_project_function,
        job_input_list=[],
    )

    assert result == []
