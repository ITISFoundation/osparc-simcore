# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

from uuid import uuid4

import pytest
from httpx import AsyncClient
from models_library.api_schemas_webserver.functions_wb_schema import (
    FunctionIDNotFoundError,
    JSONFunctionInputSchema,
    JSONFunctionOutputSchema,
)
from pytest_mock import MockerFixture
from simcore_service_api_server._meta import API_VTAG


async def test_register_function(
    client: AsyncClient,
    mock_function_register: MockerFixture,
) -> None:
    sample_function = {
        "title": "test_function",
        "function_class": "project",
        "project_id": str(uuid4()),
        "description": "A test function",
        "input_schema": JSONFunctionInputSchema().model_dump(),
        "output_schema": JSONFunctionOutputSchema().model_dump(),
        "default_inputs": None,
    }

    response = await client.post(f"{API_VTAG}/functions", json=sample_function)
    assert response.status_code == 200
    data = response.json()
    assert data["uid"] is not None
    assert data["function_class"] == sample_function["function_class"]
    assert data["project_id"] == sample_function["project_id"]
    assert data["input_schema"] == sample_function["input_schema"]
    assert data["output_schema"] == sample_function["output_schema"]
    assert data["title"] == sample_function["title"]
    assert data["description"] == sample_function["description"]


async def test_register_function_invalid(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    invalid_function = {
        "title": "test_function",
        "function_class": "invalid_class",  # Invalid class
        "project_id": str(uuid4()),
    }
    response = await client.post(f"{API_VTAG}/functions", json=invalid_function)
    assert response.status_code == 422  # Unprocessable Entity
    assert (
        "Input tag 'invalid_class' found using 'function_class' does not"
        in response.json()["errors"][0]["msg"]
    )


async def test_get_function(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    project_id = str(uuid4())
    # First, register a sample function so that it exists
    sample_function = {
        "uid": None,
        "title": "example_function",
        "function_class": "project",
        "project_id": project_id,
        "description": "An example function",
        "input_schema": JSONFunctionInputSchema().model_dump(),
        "output_schema": JSONFunctionOutputSchema().model_dump(),
        "default_inputs": None,
    }
    post_response = await client.post(f"{API_VTAG}/functions", json=sample_function)
    assert post_response.status_code == 200
    data = post_response.json()
    function_id = data["uid"]

    expected_function = {
        "uid": function_id,
        "title": "example_function",
        "description": "An example function",
        "function_class": "project",
        "project_id": project_id,
        "input_schema": JSONFunctionInputSchema().model_dump(),
        "output_schema": JSONFunctionOutputSchema().model_dump(),
        "default_inputs": None,
    }
    response = await client.get(f"{API_VTAG}/functions/{function_id}")
    assert response.status_code == 200
    data = response.json()
    assert data == expected_function


async def test_get_function_not_found(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    non_existent_function_id = str(uuid4())
    with pytest.raises(FunctionIDNotFoundError):
        await client.get(f"{API_VTAG}/functions/{non_existent_function_id}")


async def test_list_functions(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    # Register a sample function
    sample_function = {
        "uid": None,
        "title": "example_function",
        "function_class": "project",
        "project_id": str(uuid4()),
        "description": "An example function",
        "input_schema": JSONFunctionInputSchema().model_dump(),
        "output_schema": JSONFunctionOutputSchema().model_dump(),
        "default_inputs": None,
    }
    post_response = await client.post(f"{API_VTAG}/functions", json=sample_function)
    assert post_response.status_code == 200

    # List functions
    response = await client.get(
        f"{API_VTAG}/functions", params={"limit": 10, "offset": 0}
    )
    assert response.status_code == 200
    data = response.json()["items"]
    assert len(data) > 0
    assert data[0]["title"] == sample_function["title"]


async def test_update_function_title(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    project_id = str(uuid4())
    # Register a sample function
    sample_function = {
        "uid": None,
        "title": "example_function",
        "function_class": "project",
        "project_id": project_id,
        "description": "An example function",
        "input_schema": JSONFunctionInputSchema().model_dump(),
        "output_schema": JSONFunctionOutputSchema().model_dump(),
        "default_inputs": None,
    }
    post_response = await client.post(f"{API_VTAG}/functions", json=sample_function)
    assert post_response.status_code == 200
    data = post_response.json()
    function_id = data["uid"]

    # Update the function title
    updated_title = {"title": "updated_example_function"}
    response = await client.patch(
        f"{API_VTAG}/functions/{function_id}/title", params=updated_title
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == updated_title["title"]


async def test_update_function_description(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    project_id = str(uuid4())
    # Register a sample function
    sample_function = {
        "uid": None,
        "title": "example_function",
        "function_class": "project",
        "project_id": project_id,
        "description": "An example function",
        "input_schema": JSONFunctionInputSchema().model_dump(),
        "output_schema": JSONFunctionOutputSchema().model_dump(),
        "default_inputs": None,
    }
    post_response = await client.post(f"{API_VTAG}/functions", json=sample_function)
    assert post_response.status_code == 200
    data = post_response.json()
    function_id = data["uid"]

    # Update the function description
    updated_description = {"description": "updated_example_function"}
    response = await client.patch(
        f"{API_VTAG}/functions/{function_id}/description", params=updated_description
    )
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == updated_description["description"]


async def test_get_function_input_schema(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    project_id = str(uuid4())
    # Register a sample function
    sample_function = {
        "uid": None,
        "title": "example_function",
        "function_class": "project",
        "project_id": project_id,
        "description": "An example function",
        "input_schema": JSONFunctionInputSchema(
            schema_content={
                "type": "object",
                "properties": {"input1": {"type": "integer"}},
            }
        ).model_dump(),
        "output_schema": JSONFunctionOutputSchema(
            schema_content={
                "type": "object",
                "properties": {"output1": {"type": "string"}},
            }
        ).model_dump(),
        "default_inputs": None,
    }
    post_response = await client.post(f"{API_VTAG}/functions", json=sample_function)
    assert post_response.status_code == 200
    data = post_response.json()
    function_id = data["uid"]

    # Get the input schema
    # assert f"/functions/{function_id}/input-schema" is None
    response = await client.get(f"{API_VTAG}/functions/{function_id}/input_schema")
    assert response.status_code == 200
    data = response.json()
    assert data["schema_content"] == sample_function["input_schema"]["schema_content"]


async def test_get_function_output_schema(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    project_id = str(uuid4())
    # Register a sample function
    sample_function = {
        "uid": None,
        "title": "example_function",
        "function_class": "project",
        "project_id": project_id,
        "description": "An example function",
        "input_schema": JSONFunctionInputSchema().model_dump(),
        "output_schema": JSONFunctionOutputSchema(
            schema_content={
                "type": "object",
                "properties": {"output1": {"type": "string"}},
            }
        ).model_dump(),
        "default_inputs": None,
    }
    post_response = await client.post(f"{API_VTAG}/functions", json=sample_function)
    assert post_response.status_code == 200
    data = post_response.json()
    function_id = data["uid"]

    # Get the output schema
    response = await client.get(f"{API_VTAG}/functions/{function_id}/output_schema")
    assert response.status_code == 200
    data = response.json()
    assert data["schema_content"] == sample_function["output_schema"]["schema_content"]


async def test_validate_function_inputs(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    project_id = str(uuid4())
    # Register a sample function
    sample_function = {
        "uid": None,
        "title": "example_function",
        "function_class": "project",
        "project_id": project_id,
        "description": "An example function",
        "input_schema": JSONFunctionInputSchema(
            schema_content={
                "type": "object",
                "properties": {"input1": {"type": "integer"}},
            }
        ).model_dump(),
        "output_schema": JSONFunctionOutputSchema(
            schema_content={
                "type": "object",
                "properties": {"output1": {"type": "string"}},
            }
        ).model_dump(),
        "default_inputs": None,
    }
    post_response = await client.post(f"{API_VTAG}/functions", json=sample_function)
    assert post_response.status_code == 200
    data = post_response.json()
    function_id = data["uid"]

    # Validate inputs
    validate_payload = {"input1": 10}
    response = await client.post(
        f"{API_VTAG}/functions/{function_id}:validate_inputs", json=validate_payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data == [True, "Inputs are valid"]


async def test_delete_function(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    project_id = str(uuid4())
    # Register a sample function
    sample_function = {
        "uid": None,
        "title": "example_function",
        "function_class": "project",
        "project_id": project_id,
        "description": "An example function",
        "input_schema": JSONFunctionInputSchema().model_dump(),
        "output_schema": JSONFunctionOutputSchema().model_dump(),
        "default_inputs": None,
    }
    post_response = await client.post(f"{API_VTAG}/functions", json=sample_function)
    assert post_response.status_code == 200
    data = post_response.json()
    function_id = data["uid"]

    # Delete the function
    response = await client.delete(f"{API_VTAG}/functions/{function_id}")
    assert response.status_code == 200


async def test_register_function_job(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    """Test the register_function_job endpoint."""

    mock_function_job = {
        "function_uid": str(uuid4()),
        "title": "Test Function Job",
        "description": "A test function job",
        "inputs": {"key": "value"},
        "outputs": None,
        "project_job_id": str(uuid4()),
        "function_class": "project",
    }

    # Act
    response = await client.post(f"{API_VTAG}/function_jobs", json=mock_function_job)

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["uid"] is not None
    response_data.pop("uid", None)  # Remove the uid field
    mock_function_job.pop("uid", None)  # Remove the uid field
    assert response_data == mock_function_job


async def test_get_function_job(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    """Test the get_function_job endpoint."""
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
    post_response = await client.post(
        f"{API_VTAG}/function_jobs", json=mock_function_job
    )
    assert post_response.status_code == 200
    data = post_response.json()
    function_job_id = data["uid"]

    # Now, get the function job
    response = await client.get(f"{API_VTAG}/function_jobs/{function_job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["uid"] == function_job_id
    assert data["title"] == mock_function_job["title"]
    assert data["description"] == mock_function_job["description"]
    assert data["inputs"] == mock_function_job["inputs"]
    assert data["outputs"] == mock_function_job["outputs"]


async def test_list_function_jobs(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    """Test the list_function_jobs endpoint."""

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
    post_response = await client.post(
        f"{API_VTAG}/function_jobs", json=mock_function_job
    )
    assert post_response.status_code == 200

    # Now, list function jobs
    response = await client.get(f"{API_VTAG}/function_jobs")
    assert response.status_code == 200
    data = response.json()["items"]
    assert len(data) > 0
    assert data[0]["title"] == mock_function_job["title"]


async def test_delete_function_job(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    """Test the delete_function_job endpoint."""

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
    post_response = await client.post(
        f"{API_VTAG}/function_jobs", json=mock_function_job
    )
    assert post_response.status_code == 200
    data = post_response.json()
    function_job_id = data["uid"]

    # Now, delete the function job
    response = await client.delete(f"{API_VTAG}/function_jobs/{function_job_id}")
    assert response.status_code == 200


async def test_register_function_job_collection(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    mock_function_job_collection = {
        "uid": None,
        "title": "Test Collection",
        "description": "A test function job collection",
        "job_ids": [str(uuid4()), str(uuid4())],
    }

    response = await client.post(
        f"{API_VTAG}/function_job_collections", json=mock_function_job_collection
    )

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["uid"] is not None
    response_data.pop("uid", None)  # Remove the uid field
    mock_function_job_collection.pop("uid", None)  # Remove the uid field
    assert response_data == mock_function_job_collection


async def test_get_function_job_collection(
    client: AsyncClient, mock_function_register: MockerFixture
) -> None:
    # Arrange
    mock_function_job_collection = {
        "uid": None,
        "title": "Test Collection",
        "description": "A test function job collection",
        "job_ids": [str(uuid4()), str(uuid4())],
    }

    # First, register a function job collection
    post_response = await client.post(
        f"{API_VTAG}/function_job_collections", json=mock_function_job_collection
    )
    assert post_response.status_code == 200
    data = post_response.json()
    collection_id = data["uid"]

    # Act
    response = await client.get(f"{API_VTAG}/function_job_collections/{collection_id}")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["uid"] == collection_id
    assert data["title"] == mock_function_job_collection["title"]
    assert data["description"] == mock_function_job_collection["description"]
    assert data["job_ids"] == mock_function_job_collection["job_ids"]
