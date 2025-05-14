# pylint: disable=redefined-outer-name
# pylint: disable=no-value-for-parameter
# pylint: disable=super-init-not-called
# pylint: disable=unused-argument

from uuid import uuid4

import pytest
from fastapi import FastAPI
from models_library.api_schemas_webserver.functions_wb_schema import (
    Function,
    FunctionIDNotFoundError,
    FunctionJob,
    FunctionJobCollection,
    FunctionJobCollectionIDNotFoundError,
    FunctionJobIDNotFoundError,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
)
from models_library.rest_pagination import PageMetaInfoLimitOffset
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
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
            **app_environment,  # WARNING: AFTER env_devel_dict because HOST are set to 127.0.0.1 in here
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",
            "WEBSERVER_FUNCTIONS": "1",
        },
    )


class DummyRpcClient(RabbitMQRPCClient):

    def __init__(self):
        self.client_name = "dummy_client"
        self.settings = {}  # Add a settings attribute to avoid AttributeError

    async def request(self, namespace: str, method_name: str, **kwargs):
        # Mock implementation of the request method
        assert isinstance(namespace, str)
        assert isinstance(method_name, str)
        assert isinstance(kwargs, dict)
        return {"mocked_response": True}


@pytest.fixture
async def mock_wb_api_server_rpc(app: FastAPI, mocker: MockerFixture) -> MockerFixture:

    app.dependency_overrides[get_wb_api_rpc_client] = lambda: WbApiRpcClient(
        _client=DummyRpcClient()
    )
    return mocker


class MockFunctionRegister:
    def __init__(self) -> None:
        self._functions = {}
        self._function_jobs = {}
        self._function_job_collections = {}

    async def register_function(
        self, rabbitmq_rpc_client: RabbitMQRPCClient, function: Function
    ) -> RegisteredFunction:
        assert isinstance(rabbitmq_rpc_client, RabbitMQRPCClient)
        uid = uuid4()
        self._functions[uid] = TypeAdapter(RegisteredFunction).validate_python(
            {
                "uid": str(uid),
                "title": function.title,
                "function_class": function.function_class,
                "project_id": getattr(function, "project_id", None),
                "description": function.description,
                "input_schema": function.input_schema,
                "output_schema": function.output_schema,
                "default_inputs": None,
            }
        )
        return self._functions[uid]

    async def get_function(
        self, rabbitmq_rpc_client: RabbitMQRPCClient, function_id: str
    ) -> RegisteredFunction:
        assert isinstance(rabbitmq_rpc_client, RabbitMQRPCClient)
        # Mimic retrieval of a function based on function_id and raise 404 if not found
        if function_id not in self._functions:
            raise FunctionIDNotFoundError(function_id=function_id)
        return self._functions[function_id]

    async def run_function(
        self, rabbitmq_rpc_client: RabbitMQRPCClient, function_id: str, inputs: dict
    ) -> dict:
        # Mimic running a function and returning a success status
        if function_id not in self._functions:
            raise FunctionIDNotFoundError(function_id=function_id)
        return {"status": "success", "function_id": function_id, "inputs": inputs}

    async def list_functions(
        self,
        rabbitmq_rpc_client: RabbitMQRPCClient,
        pagination_offset: int = 0,
        pagination_limit: int = 10,
    ) -> tuple[list[RegisteredFunction], PageMetaInfoLimitOffset]:
        # Mimic listing all functions
        functions_list = list(self._functions.values())[
            pagination_offset : pagination_offset + pagination_limit
        ]
        total_count = len(self._functions)
        page_meta_info = PageMetaInfoLimitOffset(
            total=total_count,
            limit=pagination_limit,
            offset=pagination_offset,
            count=len(functions_list),
        )
        return functions_list, page_meta_info

    async def delete_function(
        self, rabbitmq_rpc_client: RabbitMQRPCClient, function_id: str
    ) -> None:
        # Mimic deleting a function
        if function_id in self._functions:
            del self._functions[function_id]
        else:
            raise FunctionIDNotFoundError(function_id=function_id)

    async def register_function_job(
        self, rabbitmq_rpc_client: RabbitMQRPCClient, function_job: FunctionJob
    ) -> RegisteredFunctionJob:
        # Mimic registering a function job
        uid = uuid4()
        self._function_jobs[uid] = TypeAdapter(RegisteredFunctionJob).validate_python(
            {
                "uid": str(uid),
                "function_uid": function_job.function_uid,
                "title": function_job.title,
                "description": function_job.description,
                "project_job_id": getattr(function_job, "project_job_id", None),
                "inputs": function_job.inputs,
                "outputs": function_job.outputs,
                "function_class": function_job.function_class,
            }
        )
        return self._function_jobs[uid]

    async def get_function_job(
        self, rabbitmq_rpc_client: RabbitMQRPCClient, function_job_id: str
    ) -> RegisteredFunctionJob:
        # Mimic retrieval of a function job based on function_job_id and raise 404 if not found
        if function_job_id not in self._function_jobs:
            raise FunctionJobIDNotFoundError(function_id=function_job_id)
        return self._function_jobs[function_job_id]

    async def list_function_jobs(
        self,
        rabbitmq_rpc_client: RabbitMQRPCClient,
        pagination_offset: int,
        pagination_limit: int,
    ) -> tuple[list[RegisteredFunctionJob], PageMetaInfoLimitOffset]:
        # Mimic listing all function jobs
        function_jobs_list = list(self._function_jobs.values())[
            pagination_offset : pagination_offset + pagination_limit
        ]
        total_count = len(self._function_jobs)
        page_meta_info = PageMetaInfoLimitOffset(
            total=total_count,
            limit=pagination_limit,
            offset=pagination_offset,
            count=len(function_jobs_list),
        )
        return function_jobs_list, page_meta_info

    async def delete_function_job(
        self, rabbitmq_rpc_client: RabbitMQRPCClient, function_job_id: str
    ) -> None:
        # Mimic deleting a function job
        if function_job_id in self._function_jobs:
            del self._function_jobs[function_job_id]
        else:
            raise FunctionJobIDNotFoundError(function_id=function_job_id)

    async def register_function_job_collection(
        self,
        rabbitmq_rpc_client: RabbitMQRPCClient,
        function_job_collection: FunctionJobCollection,
    ) -> RegisteredFunctionJobCollection:
        # Mimic registering a function job collection
        uid = uuid4()
        self._function_job_collections[uid] = TypeAdapter(
            RegisteredFunctionJobCollection
        ).validate_python(
            {
                "uid": str(uid),
                "title": function_job_collection.title,
                "description": function_job_collection.description,
                "job_ids": function_job_collection.job_ids,
            }
        )
        return self._function_job_collections[uid]

    async def get_function_job_collection(
        self, rabbitmq_rpc_client: RabbitMQRPCClient, function_job_collection_id: str
    ) -> RegisteredFunctionJobCollection:
        # Mimic retrieval of a function job collection based on collection_id and raise 404 if not found
        if function_job_collection_id not in self._function_job_collections:
            raise FunctionJobCollectionIDNotFoundError(
                function_job_collection_id=function_job_collection_id
            )
        return self._function_job_collections[function_job_collection_id]

    async def list_function_job_collections(
        self,
        rabbitmq_rpc_client: RabbitMQRPCClient,
        pagination_offset: int,
        pagination_limit: int,
    ) -> tuple[list[RegisteredFunctionJobCollection], PageMetaInfoLimitOffset]:
        # Mimic listing all function job collections
        function_job_collections_list = list(self._function_job_collections.values())[
            pagination_offset : pagination_offset + pagination_limit
        ]
        total_count = len(self._function_job_collections)
        page_meta_info = PageMetaInfoLimitOffset(
            total=total_count,
            limit=pagination_limit,
            offset=pagination_offset,
            count=len(function_job_collections_list),
        )
        return function_job_collections_list, page_meta_info

    async def delete_function_job_collection(
        self, rabbitmq_rpc_client: RabbitMQRPCClient, function_job_collection_id: str
    ) -> None:
        # Mimic deleting a function job collection
        if function_job_collection_id in self._function_job_collections:
            del self._function_job_collections[function_job_collection_id]
        else:
            raise FunctionJobCollectionIDNotFoundError(
                function_job_collection_id=function_job_collection_id
            )

    async def update_function_title(
        self, rabbitmq_rpc_client: RabbitMQRPCClient, function_id: str, title: str
    ) -> RegisteredFunction:
        # Mimic updating the title of a function
        if function_id not in self._functions:
            raise FunctionIDNotFoundError(function_id=function_id)
        self._functions[function_id].title = title
        return self._functions[function_id]

    async def update_function_description(
        self, rabbitmq_rpc_client: RabbitMQRPCClient, function_id: str, description: str
    ) -> RegisteredFunction:
        # Mimic updating the description of a function
        if function_id not in self._functions:
            raise FunctionIDNotFoundError(function_id=function_id)
        self._functions[function_id].description = description
        return self._functions[function_id]


@pytest.fixture()
def backend_function_register() -> MockFunctionRegister:
    """Fixture to mock the backend function register."""
    return MockFunctionRegister()


@pytest.fixture()
def mock_function_register(
    mock_wb_api_server_rpc: MockerFixture,
    backend_function_register: MockFunctionRegister,
) -> None:
    mock_wb_api_server_rpc.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.functions.functions_rpc_interface.register_function",
        backend_function_register.register_function,
    )
    mock_wb_api_server_rpc.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.functions.functions_rpc_interface.get_function",
        backend_function_register.get_function,
    )
    mock_wb_api_server_rpc.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.functions.functions_rpc_interface.run_function",
        backend_function_register.run_function,
    )
    mock_wb_api_server_rpc.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.functions.functions_rpc_interface.list_functions",
        backend_function_register.list_functions,
    )
    mock_wb_api_server_rpc.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.functions.functions_rpc_interface.delete_function",
        backend_function_register.delete_function,
    )
    mock_wb_api_server_rpc.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.functions.functions_rpc_interface.register_function_job",
        backend_function_register.register_function_job,
    )
    mock_wb_api_server_rpc.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.functions.functions_rpc_interface.get_function_job",
        backend_function_register.get_function_job,
    )
    mock_wb_api_server_rpc.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.functions.functions_rpc_interface.list_function_jobs",
        backend_function_register.list_function_jobs,
    )
    mock_wb_api_server_rpc.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.functions.functions_rpc_interface.delete_function_job",
        backend_function_register.delete_function_job,
    )
    mock_wb_api_server_rpc.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.functions.functions_rpc_interface.register_function_job_collection",
        backend_function_register.register_function_job_collection,
    )
    mock_wb_api_server_rpc.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.functions.functions_rpc_interface.get_function_job_collection",
        backend_function_register.get_function_job_collection,
    )
    mock_wb_api_server_rpc.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.functions.functions_rpc_interface.list_function_job_collections",
        backend_function_register.list_function_job_collections,
    )
    mock_wb_api_server_rpc.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.functions.functions_rpc_interface.delete_function_job_collection",
        backend_function_register.delete_function_job_collection,
    )
    mock_wb_api_server_rpc.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.functions.functions_rpc_interface.update_function_title",
        backend_function_register.update_function_title,
    )
    mock_wb_api_server_rpc.patch(
        "servicelib.rabbitmq.rpc_interfaces.webserver.functions.functions_rpc_interface.update_function_description",
        backend_function_register.update_function_description,
    )
