from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from fastapi_pagination import add_pagination
from models_library.api_schemas_webserver.functions_wb_schema import (
    Function,
    FunctionJob,
    FunctionJobCollection,
)
from models_library.rest_pagination import (
    PageMetaInfoLimitOffset,
)
from pydantic import TypeAdapter
from simcore_service_api_server.api.routes.functions_routes import (
    function_job_collections_router,
    function_job_router,
    function_router,
    get_current_user_id,
    get_wb_api_rpc_client,
)
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture(name="api_app")
def _api_app() -> FastAPI:
    fastapi_app = FastAPI()
    fastapi_app.include_router(function_router, prefix="/functions")
    fastapi_app.include_router(function_job_router, prefix="/function_jobs")
    fastapi_app.include_router(
        function_job_collections_router, prefix="/function_job_collections"
    )
    add_pagination(fastapi_app)

    # Mock authentication dependency
    async def mock_auth_dependency() -> int:
        # Mock a valid user ID
        return 100

    fastapi_app.dependency_overrides[get_current_user_id] = mock_auth_dependency

    fake_wb_api_rpc = FakeWbApiRpc()

    async def fake_get_wb_api_rpc_client() -> FakeWbApiRpc:
        return fake_wb_api_rpc

    fastapi_app.dependency_overrides[get_wb_api_rpc_client] = fake_get_wb_api_rpc_client

    mock_engine = MagicMock(spec=AsyncEngine)
    mock_engine.pool = MagicMock()
    mock_engine.pool.checkedin = MagicMock(return_value=[])
    fastapi_app.state.engine = mock_engine

    return fastapi_app


class FakeWbApiRpc:
    def __init__(self) -> None:
        self._functions = {}
        self._function_jobs = {}
        self._function_job_collections = {}

    async def register_function(self, function: Function) -> Function:
        # Mimic returning the same function that was passed and store it for later retrieval
        function.uid = uuid4()
        self._functions[function.uid] = TypeAdapter(Function).validate_python(
            {
                "uid": str(function.uid),
                "title": function.title,
                "function_class": function.function_class,
                "project_id": getattr(function, "project_id", None),
                "description": function.description,
                "input_schema": function.input_schema,
                "output_schema": function.output_schema,
                "default_inputs": None,
            }
        )
        return self._functions[function.uid]

    async def get_function(self, function_id: str) -> dict:
        # Mimic retrieval of a function based on function_id and raise 404 if not found
        if function_id not in self._functions:
            raise HTTPException(status_code=404, detail="Function not found")
        return self._functions[function_id]

    async def run_function(self, function_id: str, inputs: dict) -> dict:
        # Mimic running a function and returning a success status
        if function_id not in self._functions:
            raise HTTPException(
                status_code=404,
                detail=f"Function {function_id} not found in {self._functions}",
            )
        return {"status": "success", "function_id": function_id, "inputs": inputs}

    async def list_functions(
        self,
        pagination_offset: int,
        pagination_limit: int,
    ) -> tuple[list[Function], PageMetaInfoLimitOffset]:
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

    async def delete_function(self, function_id: str) -> None:
        # Mimic deleting a function
        if function_id in self._functions:
            del self._functions[function_id]
        else:
            raise HTTPException(status_code=404, detail="Function not found")

    async def register_function_job(self, function_job: FunctionJob) -> FunctionJob:
        # Mimic registering a function job
        function_job.uid = uuid4()
        self._function_jobs[function_job.uid] = TypeAdapter(
            FunctionJob
        ).validate_python(
            {
                "uid": str(function_job.uid),
                "function_uid": function_job.function_uid,
                "title": function_job.title,
                "description": function_job.description,
                "project_job_id": getattr(function_job, "project_job_id", None),
                "inputs": function_job.inputs,
                "outputs": function_job.outputs,
                "function_class": function_job.function_class,
            }
        )
        return self._function_jobs[function_job.uid]

    async def get_function_job(self, function_job_id: str) -> dict:
        # Mimic retrieval of a function job based on function_job_id and raise 404 if not found
        if function_job_id not in self._function_jobs:
            raise HTTPException(status_code=404, detail="Function job not found")
        return self._function_jobs[function_job_id]

    async def list_function_jobs(
        self,
        pagination_offset: int,
        pagination_limit: int,
    ) -> tuple[list[FunctionJob], PageMetaInfoLimitOffset]:
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

    async def delete_function_job(self, function_job_id: str) -> None:
        # Mimic deleting a function job
        if function_job_id in self._function_jobs:
            del self._function_jobs[function_job_id]
        else:
            raise HTTPException(status_code=404, detail="Function job not found")

    async def register_function_job_collection(
        self, function_job_collection: FunctionJobCollection
    ) -> FunctionJobCollection:
        # Mimic registering a function job collection
        function_job_collection.uid = uuid4()
        self._function_job_collections[function_job_collection.uid] = TypeAdapter(
            FunctionJobCollection
        ).validate_python(
            {
                "uid": str(function_job_collection.uid),
                "title": function_job_collection.title,
                "description": function_job_collection.description,
                "job_ids": function_job_collection.job_ids,
            }
        )
        return self._function_job_collections[function_job_collection.uid]

    async def get_function_job_collection(
        self, function_job_collection_id: str
    ) -> dict:
        # Mimic retrieval of a function job collection based on collection_id and raise 404 if not found
        if function_job_collection_id not in self._function_job_collections:
            raise HTTPException(
                status_code=404, detail="Function job collection not found"
            )
        return self._function_job_collections[function_job_collection_id]

    async def list_function_job_collections(
        self,
        pagination_offset: int,
        pagination_limit: int,
    ) -> tuple[list[FunctionJobCollection], PageMetaInfoLimitOffset]:
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
        self, function_job_collection_id: str
    ) -> None:
        # Mimic deleting a function job collection
        if function_job_collection_id in self._function_job_collections:
            del self._function_job_collections[function_job_collection_id]
        else:
            raise HTTPException(
                status_code=404, detail="Function job collection not found"
            )


def test_register_function(api_app) -> None:
    client = TestClient(api_app)
    sample_function = {
        "uid": None,
        "title": "test_function",
        "function_class": "project",
        "project_id": str(uuid4()),
        "description": "A test function",
        "input_schema": {"schema_dict": {}},
        "output_schema": {"schema_dict": {}},
        "default_inputs": None,
    }
    response = client.post("/functions", json=sample_function)
    assert response.status_code == 200
    data = response.json()
    assert data["uid"] is not None
    assert data["function_class"] == sample_function["function_class"]
    assert data["project_id"] == sample_function["project_id"]
    assert data["input_schema"] == sample_function["input_schema"]
    assert data["output_schema"] == sample_function["output_schema"]
    assert data["title"] == sample_function["title"]
    assert data["description"] == sample_function["description"]


def test_register_function_invalid(api_app: FastAPI) -> None:
    client = TestClient(api_app)
    invalid_function = {
        "title": "test_function",
        "function_class": "invalid_class",  # Invalid class
        "project_id": str(uuid4()),
    }
    response = client.post("/functions", json=invalid_function)
    assert response.status_code == 422  # Unprocessable Entity
    assert (
        "Input tag 'invalid_class' found using 'function_class' does no"
        in response.json()["detail"][0]["msg"]
    )


def test_get_function(api_app: FastAPI) -> None:
    client = TestClient(api_app)
    project_id = str(uuid4())
    # First, register a sample function so that it exists
    sample_function = {
        "uid": None,
        "title": "example_function",
        "function_class": "project",
        "project_id": project_id,
        "description": "An example function",
        "input_schema": {"schema_dict": {}},
        "output_schema": {"schema_dict": {}},
        "default_inputs": None,
    }
    post_response = client.post("/functions", json=sample_function)
    assert post_response.status_code == 200
    data = post_response.json()
    function_id = data["uid"]

    expected_function = {
        "uid": function_id,
        "title": "example_function",
        "description": "An example function",
        "function_class": "project",
        "project_id": project_id,
        "input_schema": {"schema_dict": {}},
        "output_schema": {"schema_dict": {}},
        "default_inputs": None,
    }
    response = client.get(f"/functions/{function_id}")
    assert response.status_code == 200
    data = response.json()
    # Exclude the 'project_id' field from both expected and actual results before comparing
    assert data == expected_function


def test_get_function_not_found(api_app: FastAPI) -> None:
    client = TestClient(api_app)
    non_existent_function_id = str(uuid4())
    response = client.get(f"/functions/{non_existent_function_id}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Function not found"}


def test_list_functions(api_app: FastAPI) -> None:
    client = TestClient(api_app)
    # Register a sample function
    sample_function = {
        "uid": None,
        "title": "example_function",
        "function_class": "project",
        "project_id": str(uuid4()),
        "description": "An example function",
        "input_schema": {"schema_dict": {}},
        "output_schema": {"schema_dict": {}},
        "default_inputs": None,
    }
    post_response = client.post("/functions", json=sample_function)
    assert post_response.status_code == 200

    # List functions
    response = client.get("/functions", params={"limit": 10, "offset": 0})
    assert response.status_code == 200
    data = response.json()["items"]
    assert len(data) > 0
    assert data[0]["title"] == sample_function["title"]


def test_get_function_input_schema(api_app: FastAPI) -> None:
    client = TestClient(api_app)
    project_id = str(uuid4())
    # Register a sample function
    sample_function = {
        "uid": None,
        "title": "example_function",
        "function_class": "project",
        "project_id": project_id,
        "description": "An example function",
        "input_schema": {
            "schema_dict": {
                "type": "object",
                "properties": {"input1": {"type": "integer"}},
            }
        },
        "output_schema": {"schema_dict": {}},
        "default_inputs": None,
    }
    post_response = client.post("/functions", json=sample_function)
    assert post_response.status_code == 200
    data = post_response.json()
    function_id = data["uid"]

    # Get the input schema
    # assert f"/functions/{function_id}/input-schema" is None
    response = client.get(f"/functions/{function_id}/input_schema")
    assert response.status_code == 200
    data = response.json()
    assert data["schema_dict"] == sample_function["input_schema"]["schema_dict"]


def test_get_function_output_schema(api_app: FastAPI) -> None:
    client = TestClient(api_app)
    project_id = str(uuid4())
    # Register a sample function
    sample_function = {
        "uid": None,
        "title": "example_function",
        "function_class": "project",
        "project_id": project_id,
        "description": "An example function",
        "input_schema": {"schema_dict": {}},
        "output_schema": {
            "schema_dict": {
                "type": "object",
                "properties": {"output1": {"type": "string"}},
            }
        },
        "default_inputs": None,
    }
    post_response = client.post("/functions", json=sample_function)
    assert post_response.status_code == 200
    data = post_response.json()
    function_id = data["uid"]

    # Get the output schema
    response = client.get(f"/functions/{function_id}/output_schema")
    assert response.status_code == 200
    data = response.json()
    assert data["schema_dict"] == sample_function["output_schema"]["schema_dict"]


def test_validate_function_inputs(api_app: FastAPI) -> None:
    client = TestClient(api_app)
    project_id = str(uuid4())
    # Register a sample function
    sample_function = {
        "uid": None,
        "title": "example_function",
        "function_class": "project",
        "project_id": project_id,
        "description": "An example function",
        "input_schema": {
            "schema_dict": {
                "type": "object",
                "properties": {"input1": {"type": "integer"}},
            }
        },
        "output_schema": {"schema_dict": {}},
        "default_inputs": None,
    }
    post_response = client.post("/functions", json=sample_function)
    assert post_response.status_code == 200
    data = post_response.json()
    function_id = data["uid"]

    # Validate inputs
    validate_payload = {"input1": 10}
    response = client.post(
        f"/functions/{function_id}:validate_inputs", json=validate_payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data == [True, "Inputs are valid"]


def test_delete_function(api_app: FastAPI) -> None:
    client = TestClient(api_app)
    project_id = str(uuid4())
    # Register a sample function
    sample_function = {
        "uid": None,
        "title": "example_function",
        "function_class": "project",
        "project_id": project_id,
        "description": "An example function",
        "input_schema": {"schema_dict": {}},
        "output_schema": {"schema_dict": {}},
        "default_inputs": None,
    }
    post_response = client.post("/functions", json=sample_function)
    assert post_response.status_code == 200
    data = post_response.json()
    function_id = data["uid"]

    # Delete the function
    response = client.delete(f"/functions/{function_id}")
    assert response.status_code == 200


def test_register_function_job(api_app: FastAPI) -> None:
    """Test the register_function_job endpoint."""

    client = TestClient(api_app)
    mock_function_job = {
        "uid": None,
        "function_uid": str(uuid4()),
        "title": "Test Function Job",
        "description": "A test function job",
        "inputs": {"key": "value"},
        "outputs": None,
        "project_job_id": str(uuid4()),
        "function_class": "project",
    }

    # Act
    response = client.post("/function_jobs", json=mock_function_job)

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["uid"] is not None
    response_data.pop("uid", None)  # Remove the uid field
    mock_function_job.pop("uid", None)  # Remove the uid field
    assert response_data == mock_function_job


def test_get_function_job(api_app: FastAPI) -> None:
    """Test the get_function_job endpoint."""

    client = TestClient(api_app)
    mock_function_job = {
        "uid": None,
        "function_uid": str(uuid4()),
        "title": "Test Function Job",
        "description": "A test function job",
        "inputs": {"key": "value"},
        "outputs": None,
        "project_job_id": str(uuid4()),
        "function_class": "project",
    }

    # First, register a function job
    post_response = client.post("/function_jobs", json=mock_function_job)
    assert post_response.status_code == 200
    data = post_response.json()
    function_job_id = data["uid"]

    # Now, get the function job
    response = client.get(f"/function_jobs/{function_job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["uid"] == function_job_id
    assert data["title"] == mock_function_job["title"]
    assert data["description"] == mock_function_job["description"]
    assert data["inputs"] == mock_function_job["inputs"]
    assert data["outputs"] == mock_function_job["outputs"]


def test_list_function_jobs(api_app: FastAPI) -> None:
    """Test the list_function_jobs endpoint."""

    client = TestClient(api_app)
    mock_function_job = {
        "uid": None,
        "function_uid": str(uuid4()),
        "title": "Test Function Job",
        "description": "A test function job",
        "inputs": {"key": "value"},
        "outputs": None,
        "project_job_id": str(uuid4()),
        "function_class": "project",
    }

    # First, register a function job
    post_response = client.post("/function_jobs", json=mock_function_job)
    assert post_response.status_code == 200

    # Now, list function jobs
    response = client.get("/function_jobs")
    assert response.status_code == 200
    data = response.json()["items"]
    assert len(data) > 0
    assert data[0]["title"] == mock_function_job["title"]


def test_delete_function_job(api_app: FastAPI) -> None:
    """Test the delete_function_job endpoint."""

    client = TestClient(api_app)
    mock_function_job = {
        "uid": None,
        "function_uid": str(uuid4()),
        "title": "Test Function Job",
        "description": "A test function job",
        "inputs": {"key": "value"},
        "outputs": None,
        "project_job_id": str(uuid4()),
        "function_class": "project",
    }

    # First, register a function job
    post_response = client.post("/function_jobs", json=mock_function_job)
    assert post_response.status_code == 200
    data = post_response.json()
    function_job_id = data["uid"]

    # Now, delete the function job
    response = client.delete(f"/function_jobs/{function_job_id}")
    assert response.status_code == 200


def test_register_function_job_collection(api_app: FastAPI) -> None:
    # Arrange
    client = TestClient(api_app)

    mock_function_job_collection = {
        "uid": None,
        "title": "Test Collection",
        "description": "A test function job collection",
        "job_ids": [str(uuid4()), str(uuid4())],
    }

    # Act
    response = client.post(
        "/function_job_collections", json=mock_function_job_collection
    )

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["uid"] is not None
    response_data.pop("uid", None)  # Remove the uid field
    mock_function_job_collection.pop("uid", None)  # Remove the uid field
    assert response_data == mock_function_job_collection


def test_get_function_job_collection(api_app: FastAPI) -> None:
    # Arrange
    client = TestClient(api_app)
    mock_function_job_collection = {
        "uid": None,
        "title": "Test Collection",
        "description": "A test function job collection",
        "job_ids": [str(uuid4()), str(uuid4())],
    }

    # First, register a function job collection
    post_response = client.post(
        "/function_job_collections", json=mock_function_job_collection
    )
    assert post_response.status_code == 200
    data = post_response.json()
    collection_id = data["uid"]

    # Act
    response = client.get(f"/function_job_collections/{collection_id}")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["uid"] == collection_id
    assert data["title"] == mock_function_job_collection["title"]
    assert data["description"] == mock_function_job_collection["description"]
    assert data["job_ids"] == mock_function_job_collection["job_ids"]


# def test_run_function_project_class(api_app: FastAPI) -> None:
#     client = TestClient(api_app)
#     project_id = str(uuid4())
#     # Register a sample function with "project" class
#     sample_function = {
#         "title": "example_function",
#         "function_class": "project",
#         "project_id": project_id,
#         "description": "An example function",
#         "input_schema": {"schema_dict": {"type": "object", "properties": {"input1": {"type": "integer"}}}},
#         "output_schema": {"schema_dict": {}},
#         "default_inputs": {"input1": 5},
#     }
#     post_response = client.post("/functions", json=sample_function)
#     assert post_response.status_code == 200
#     data = post_response.json()
#     function_id = data["uid"]

#     # Run the function
#     run_payload = {"input1": 10}
#     response = client.post(f"/functions/{function_id}:run", json=run_payload)
#     assert response.status_code == 200
#     data = response.json()
#     assert data["function_uid"] == function_id
#     assert data["inputs"] == {"input1": 10}

# def test_run_function_solver_class(api_app: FastAPI) -> None:
#     client = TestClient(api_app)
#     # Register a sample function with "solver" class
#     sample_function = {
#         "title": "solver_function",
#         "function_class": "solver",
#         "solver_key": "example_solver",
#         "solver_version": "1.0.0",
#         "description": "A solver function",
#         "input_schema": {"schema_dict": {"type": "object", "properties": {"input1": {"type": "integer"}}}},
#         "output_schema": {"schema_dict": {}},
#         "default_inputs": {"input1": 5},
#     }
#     post_response = client.post("/functions", json=sample_function)
#     assert post_response.status_code == 200
#     data = post_response.json()
#     function_id = data["uid"]

#     # Run the function
#     run_payload = {"input1": 15}
#     response = client.post(f"/functions/{function_id}:run", json=run_payload)
#     assert response.status_code == 200
#     data = response.json()
#     assert data["function_uid"] == function_id
#     assert data["inputs"] == {"input1": 15}

# def test_run_function_invalid_inputs(api_app: FastAPI) -> None:
#     client = TestClient(api_app)
#     # Register a sample function with input schema
#     sample_function = {
#         "title": "example_function",
#         "function_class": "project",
#         "project_id": str(uuid4()),
#         "description": "An example function",
#         "input_schema": {"schema_dict": {"type": "object", "properties": {"input1": {"type": "integer"}}}},
#         "output_schema": {"schema_dict": {}},
#     }
#     post_response = client.post("/functions", json=sample_function)
#     assert post_response.status_code == 200
#     data = post_response.json()
#     function_id = data["uid"]

#     # Run the function with invalid inputs
#     run_payload = {"input1": "invalid_value"}
#     response = client.post(f"/functions/{function_id}:run", json=run_payload)
#     assert response.status_code == 400
#     assert "inputs are not valid" in response.json()["detail"]

# def test_run_function_not_found(api_app: FastAPI) -> None:
#     client = TestClient(api_app)
#     non_existent_function_id = str(uuid4())
#     run_payload = {"input1": 10}
#     response = client.post(f"/functions/{non_existent_function_id}:run", json=run_payload)
#     assert response.status_code == 404
#     assert response.json() == {"detail": "Function not found"}

# def test_run_function_cached_job(api_app: FastAPI) -> None:
#     client = TestClient(api_app)
#     # Register a sample function
#     sample_function = {
#         "title": "example_function",
#         "function_class": "project",
#         "project_id": str(uuid4()),
#         "description": "An example function",
#         "input_schema": {"schema_dict": {"type": "object", "properties": {"input1": {"type": "integer"}}}},
#         "output_schema": {"schema_dict": {}},
#         "default_inputs": {"input1": 5},
#     }
#     post_response = client.post("/functions", json=sample_function)
#     assert post_response.status_code == 200
#     data = post_response.json()
#     function_id = data["uid"]

#     # Mimic a cached job
#     run_payload = {"input1": 10}
#     response = client.post(f"/functions/{function_id}:run", json=run_payload)
#     assert response.status_code == 200
#     data = response.json()
#     assert data["function_uid"] == function_id
#     assert data["inputs"] == {"input1": 10}
