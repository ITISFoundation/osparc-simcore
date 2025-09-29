# pylint: disable=redefined-outer-name
# pylint: disable=no-value-for-parameter
# pylint: disable=super-init-not-called
# pylint: disable=unused-argument
# pylint: disable=no-self-use
# pylint: disable=cyclic-import

import datetime
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from models_library.api_schemas_webserver.functions import (
    Function,
    FunctionClass,
    FunctionJob,
    FunctionJobCollection,
    JSONFunctionInputSchema,
    JSONFunctionOutputSchema,
    ProjectFunction,
    ProjectFunctionJob,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
)
from models_library.functions import (
    RegisteredFunctionJobCollection,
    RegisteredSolverFunction,
    RegisteredSolverFunctionJob,
    SolverFunctionJob,
)
from models_library.functions_errors import FunctionIDNotFoundError
from models_library.projects import ProjectID
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from simcore_service_api_server.api.dependencies import services
from simcore_service_api_server.api.dependencies.services import get_rabbitmq_rpc_client
from simcore_service_api_server.api.routes.functions_routes import get_wb_api_rpc_client
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
):
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",
            "WEBSERVER_FUNCTIONS": "1",
        },
    )


class DummyRpcClient(RabbitMQRPCClient):

    def __init__(self):
        self.client_name = "dummy_client"
        self.settings = {}  # type: ignore # Add a settings attribute to avoid AttributeError

    async def request(self, namespace: str, method_name: str, **kwargs):
        # Mock implementation of the request method
        assert isinstance(namespace, str)
        assert isinstance(method_name, str)
        assert isinstance(kwargs, dict)
        return {"mocked_response": True}


@pytest.fixture
async def mock_rabbitmq_rpc_client(
    app: FastAPI, mocker: MockerFixture
) -> MockerFixture:
    def _():
        return DummyRpcClient()

    app.dependency_overrides[get_rabbitmq_rpc_client] = _
    return mocker


@pytest.fixture
async def mock_celery_task_manager(app: FastAPI, mocker: MockerFixture) -> MockType:
    def _(app: FastAPI):
        return None

    return mocker.patch.object(services, services.get_task_manager.__name__, _)


@pytest.fixture
async def mock_wb_api_server_rpc(app: FastAPI, mocker: MockerFixture) -> MockerFixture:
    from servicelib.rabbitmq.rpc_interfaces.webserver.v1 import WebServerRpcClient

    app.dependency_overrides[get_wb_api_rpc_client] = lambda: WbApiRpcClient(
        _client=DummyRpcClient(),
        _rpc_client=mocker.MagicMock(spec=WebServerRpcClient),
    )
    return mocker


@pytest.fixture
def sample_input_schema() -> JSONFunctionInputSchema:
    return JSONFunctionInputSchema(
        schema_content={
            "type": "object",
            "properties": {"input1": {"type": "integer"}},
        }
    )


@pytest.fixture
def sample_output_schema() -> JSONFunctionOutputSchema:
    return JSONFunctionOutputSchema(
        schema_content={
            "type": "object",
            "properties": {"output1": {"type": "string"}},
        }
    )


@pytest.fixture
def raise_function_id_not_found() -> FunctionIDNotFoundError:
    return FunctionIDNotFoundError(function_id="function_id")


@pytest.fixture
def mock_function(
    project_id: ProjectID,
    sample_input_schema: JSONFunctionInputSchema,
    sample_output_schema: JSONFunctionOutputSchema,
) -> Function:
    sample_fields = {
        "title": "test_function",
        "function_class": FunctionClass.PROJECT,
        "project_id": str(project_id),
        "description": "A test function",
        "input_schema": sample_input_schema,
        "output_schema": sample_output_schema,
        "default_inputs": None,
    }
    return ProjectFunction(**sample_fields)


@pytest.fixture
def mock_registered_project_function(mock_function: Function) -> RegisteredFunction:
    return RegisteredProjectFunction(
        **{
            **mock_function.model_dump(),
            "uid": f"{uuid4()}",
            "created_at": datetime.datetime.now(datetime.UTC),
            "modified_at": datetime.datetime.now(datetime.UTC),
        }
    )


@pytest.fixture
def mock_registered_solver_function(
    mock_function: Function,
    sample_input_schema: JSONFunctionInputSchema,
    sample_output_schema: JSONFunctionOutputSchema,
) -> RegisteredFunction:
    return RegisteredSolverFunction(
        title="test_function",
        function_class=FunctionClass.SOLVER,
        description="A test function",
        input_schema=sample_input_schema,
        output_schema=sample_output_schema,
        default_inputs=None,
        uid=uuid4(),
        created_at=datetime.datetime.now(datetime.UTC),
        modified_at=datetime.datetime.now(datetime.UTC),
        solver_key="simcore/services/comp/ans-model",
        solver_version="1.0.1",
    )


@pytest.fixture
def mock_project_function_job(
    mock_registered_project_function: RegisteredFunction,
) -> FunctionJob:
    mock_function_job = {
        "function_uid": mock_registered_project_function.uid,
        "title": "Test Function Job",
        "description": "A test function job",
        "inputs": {"key": "value"},
        "outputs": None,
        "project_job_id": f"{uuid4()}",
        "function_class": FunctionClass.PROJECT,
        "job_creation_task_id": None,
    }
    return ProjectFunctionJob(**mock_function_job)


@pytest.fixture
def mock_registered_project_function_job(
    mock_project_function_job: FunctionJob,
) -> RegisteredFunctionJob:
    return RegisteredProjectFunctionJob(
        **{
            **mock_project_function_job.model_dump(),
            "uid": f"{uuid4()}",
            "created_at": datetime.datetime.now(datetime.UTC),
        }
    )


@pytest.fixture
def mock_solver_function_job(
    mock_registered_solver_function: RegisteredFunction,
) -> FunctionJob:
    return SolverFunctionJob(
        title="Test Function Job",
        description="A test function job",
        function_uid=mock_registered_solver_function.uid,
        inputs={"key": "value"},
        outputs=None,
        function_class=FunctionClass.SOLVER,
        solver_job_id=ProjectID(f"{uuid4()}"),
        job_creation_task_id=None,
    )


@pytest.fixture
def mock_registered_solver_function_job(
    mock_solver_function_job: FunctionJob,
) -> RegisteredFunctionJob:
    return RegisteredSolverFunctionJob(
        **{
            **mock_solver_function_job.model_dump(),
            "uid": f"{uuid4()}",
            "created_at": datetime.datetime.now(datetime.UTC),
        }
    )


@pytest.fixture
def mock_function_job_collection(
    mock_registered_project_function_job: RegisteredFunctionJob,
) -> FunctionJobCollection:
    mock_function_job_collection = {
        "title": "Test Function Job Collection",
        "description": "A test function job collection",
        "function_uid": mock_registered_project_function_job.function_uid,
        "function_class": FunctionClass.PROJECT,
        "project_id": f"{uuid4()}",
        "function_job_ids": [
            mock_registered_project_function_job.uid for _ in range(5)
        ],
    }
    return FunctionJobCollection(**mock_function_job_collection)


@pytest.fixture
def mock_registered_function_job_collection(
    mock_function_job_collection: FunctionJobCollection,
) -> RegisteredFunctionJobCollection:
    return RegisteredFunctionJobCollection(
        **{
            **mock_function_job_collection.model_dump(),
            "uid": f"{uuid4()}",
            "created_at": datetime.datetime.now(datetime.UTC),
        }
    )


@pytest.fixture()
def mock_handler_in_functions_rpc_interface(
    mock_wb_api_server_rpc: MockerFixture,
) -> Callable[[str, Any, Exception | None, Callable | None], MockType]:
    def _mock(
        handler_name: str = "",
        return_value: Any = None,
        exception: Exception | None = None,
        side_effect: Callable | None = None,
    ) -> MockType:
        from servicelib.rabbitmq.rpc_interfaces.webserver.functions import (
            functions_rpc_interface,
        )

        assert exception is None or side_effect is None

        return mock_wb_api_server_rpc.patch.object(
            functions_rpc_interface,
            handler_name,
            return_value=return_value,
            side_effect=exception or side_effect,
        )

    return _mock


@pytest.fixture()
def mock_method_in_jobs_service(
    mock_wb_api_server_rpc: MockerFixture,
) -> Callable[[str, Any, Exception | None], None]:
    def _mock(
        method_name: str = "",
        return_value: Any = None,
        exception: Exception | None = None,
    ) -> None:
        from simcore_service_api_server._service_jobs import JobService

        mock_wb_api_server_rpc.patch.object(
            JobService,
            method_name,
            return_value=return_value,
            side_effect=exception,
        )

    return _mock
