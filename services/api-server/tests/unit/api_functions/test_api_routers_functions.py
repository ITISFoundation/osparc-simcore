# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from models_library.api_schemas_webserver.functions import (
    FunctionIDNotFoundError,
    FunctionJobCollection,
    ProjectFunction,
    ProjectFunctionJob,
    RegisteredFunctionJobCollection,
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
)
from models_library.rest_pagination import PageMetaInfoLimitOffset
from servicelib.aiohttp import status
from simcore_service_api_server._meta import API_VTAG


async def test_register_function(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_function: ProjectFunction,
) -> None:
    registered_function = RegisteredProjectFunction(
        **{**mock_function.model_dump(), "uid": str(uuid4())}
    )

    mock_handler_in_functions_rpc_interface("register_function", registered_function)
    response = await client.post(
        f"{API_VTAG}/functions",
        json=mock_function.model_dump(mode="json"),
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    returned_function = RegisteredProjectFunction.model_validate(data)
    assert returned_function.uid is not None
    assert returned_function == registered_function


async def test_register_function_invalid(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
) -> None:
    invalid_function = {
        "title": "test_function",
        "function_class": "invalid_class",  # Invalid class
        "project_id": str(uuid4()),
    }
    response = await client.post(f"{API_VTAG}/functions", json=invalid_function)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert (
        "Input tag 'invalid_class' found using 'function_class' does not"
        in response.json()["errors"][0]["msg"]
    )


async def test_get_function(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function: RegisteredProjectFunction,
) -> None:
    function_id = str(uuid4())

    mock_handler_in_functions_rpc_interface("get_function", mock_registered_function)
    response = await client.get(f"{API_VTAG}/functions/{function_id}")
    assert response.status_code == status.HTTP_200_OK
    returned_function = RegisteredProjectFunction.model_validate(response.json())
    assert returned_function == mock_registered_function


async def test_get_function_not_found(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[
        [str, Any, Exception | None], None
    ],
) -> None:
    non_existent_function_id = str(uuid4())

    mock_handler_in_functions_rpc_interface(
        "get_function",
        None,
        FunctionIDNotFoundError(function_id=non_existent_function_id),
    )
    with pytest.raises(FunctionIDNotFoundError):
        await client.get(f"{API_VTAG}/functions/{non_existent_function_id}")


async def test_list_functions(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function: RegisteredProjectFunction,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "list_functions",
        (
            [mock_registered_function for _ in range(5)],
            PageMetaInfoLimitOffset(total=5, count=5, limit=10, offset=0),
        ),
    )

    response = await client.get(
        f"{API_VTAG}/functions", params={"limit": 10, "offset": 0}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["items"]
    assert len(data) == 5
    assert data[0]["title"] == mock_registered_function.title


async def test_update_function_title(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function: RegisteredProjectFunction,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "update_function_title",
        RegisteredProjectFunction(
            **{
                **mock_registered_function.model_dump(),
                "title": "updated_example_function",
            }
        ),
    )

    # Update the function title
    updated_title = {"title": "updated_example_function"}
    response = await client.patch(
        f"{API_VTAG}/functions/{mock_registered_function.uid}/title",
        params=updated_title,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["title"] == updated_title["title"]


async def test_update_function_description(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function: RegisteredProjectFunction,
) -> None:
    mock_handler_in_functions_rpc_interface(
        "update_function_description",
        RegisteredProjectFunction(
            **{
                **mock_registered_function.model_dump(),
                "description": "updated_example_function",
            }
        ),
    )

    # Update the function description
    updated_description = {"description": "updated_example_function"}
    response = await client.patch(
        f"{API_VTAG}/functions/{mock_registered_function.uid}/description",
        params=updated_description,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["description"] == updated_description["description"]


async def test_get_function_input_schema(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function: RegisteredProjectFunction,
) -> None:

    mock_handler_in_functions_rpc_interface("get_function", mock_registered_function)

    response = await client.get(
        f"{API_VTAG}/functions/{mock_registered_function.uid}/input_schema"
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert (
        data["schema_content"] == mock_registered_function.input_schema.schema_content
    )


async def test_get_function_output_schema(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function: RegisteredProjectFunction,
) -> None:

    mock_handler_in_functions_rpc_interface("get_function", mock_registered_function)

    response = await client.get(
        f"{API_VTAG}/functions/{mock_registered_function.uid}/output_schema"
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert (
        data["schema_content"] == mock_registered_function.output_schema.schema_content
    )


async def test_validate_function_inputs(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function: RegisteredProjectFunction,
) -> None:

    mock_handler_in_functions_rpc_interface("get_function", mock_registered_function)

    # Validate inputs
    validate_payload = {"input1": 10}
    response = await client.post(
        f"{API_VTAG}/functions/{mock_registered_function.uid}:validate_inputs",
        json=validate_payload,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data == [True, "Inputs are valid"]


async def test_delete_function(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function: RegisteredProjectFunction,
) -> None:
    mock_handler_in_functions_rpc_interface("delete_function", None)

    # Delete the function
    response = await client.delete(
        f"{API_VTAG}/functions/{mock_registered_function.uid}"
    )
    assert response.status_code == status.HTTP_200_OK


async def test_register_function_job(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_function_job: ProjectFunctionJob,
    mock_registered_function_job: RegisteredProjectFunctionJob,
) -> None:
    """Test the register_function_job endpoint."""

    mock_handler_in_functions_rpc_interface(
        "register_function_job", mock_registered_function_job
    )

    response = await client.post(
        f"{API_VTAG}/function_jobs", json=mock_function_job.model_dump(mode="json")
    )

    assert response.status_code == status.HTTP_200_OK
    assert (
        RegisteredProjectFunctionJob.model_validate(response.json())
        == mock_registered_function_job
    )


async def test_get_function_job(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function_job: RegisteredProjectFunctionJob,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "get_function_job", mock_registered_function_job
    )

    # Now, get the function job
    response = await client.get(
        f"{API_VTAG}/function_jobs/{mock_registered_function_job.uid}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert (
        RegisteredProjectFunctionJob.model_validate(response.json())
        == mock_registered_function_job
    )


async def test_list_function_jobs(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function_job: RegisteredProjectFunctionJob,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "list_function_jobs",
        (
            [mock_registered_function_job for _ in range(5)],
            PageMetaInfoLimitOffset(total=5, count=5, limit=10, offset=0),
        ),
    )

    # Now, list function jobs
    response = await client.get(f"{API_VTAG}/function_jobs")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["items"]
    assert len(data) == 5
    assert (
        RegisteredProjectFunctionJob.model_validate(data[0])
        == mock_registered_function_job
    )


async def test_list_function_jobs_with_function_filter(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function_job: RegisteredProjectFunctionJob,
    mock_registered_function: RegisteredProjectFunction,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "list_function_jobs",
        (
            [mock_registered_function_job for _ in range(5)],
            PageMetaInfoLimitOffset(total=5, count=5, limit=10, offset=0),
        ),
    )

    # Now, list function jobs with a filter
    response = await client.get(
        f"{API_VTAG}/functions/{mock_registered_function.uid}/jobs"
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()["items"]
    assert len(data) == 5
    assert (
        RegisteredProjectFunctionJob.model_validate(data[0])
        == mock_registered_function_job
    )


async def test_delete_function_job(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function_job: RegisteredProjectFunctionJob,
) -> None:

    mock_handler_in_functions_rpc_interface("delete_function_job", None)

    # Now, delete the function job
    response = await client.delete(
        f"{API_VTAG}/function_jobs/{mock_registered_function_job.uid}"
    )
    assert response.status_code == status.HTTP_200_OK


async def test_register_function_job_collection(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
) -> None:
    mock_function_job_collection = FunctionJobCollection.model_validate(
        {
            "title": "Test Collection",
            "description": "A test function job collection",
            "job_ids": [str(uuid4()), str(uuid4())],
        }
    )

    mock_registered_function_job_collection = (
        RegisteredFunctionJobCollection.model_validate(
            {
                **mock_function_job_collection.model_dump(),
                "uid": str(uuid4()),
            }
        )
    )

    mock_handler_in_functions_rpc_interface(
        "register_function_job_collection", mock_registered_function_job_collection
    )

    response = await client.post(
        f"{API_VTAG}/function_job_collections",
        json=mock_function_job_collection.model_dump(mode="json"),
    )

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert (
        RegisteredFunctionJobCollection.model_validate(response.json())
        == mock_registered_function_job_collection
    )


async def test_get_function_job_collection(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
) -> None:
    mock_registered_function_job_collection = (
        RegisteredFunctionJobCollection.model_validate(
            {
                "uid": str(uuid4()),
                "title": "Test Collection",
                "description": "A test function job collection",
                "job_ids": [str(uuid4()), str(uuid4())],
            }
        )
    )

    mock_handler_in_functions_rpc_interface(
        "get_function_job_collection", mock_registered_function_job_collection
    )

    response = await client.get(
        f"{API_VTAG}/function_job_collections/{mock_registered_function_job_collection.uid}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert (
        RegisteredFunctionJobCollection.model_validate(response.json())
        == mock_registered_function_job_collection
    )


async def test_list_function_job_collections(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
) -> None:
    mock_registered_function_job_collection = (
        RegisteredFunctionJobCollection.model_validate(
            {
                "uid": str(uuid4()),
                "title": "Test Collection",
                "description": "A test function job collection",
                "job_ids": [str(uuid4()), str(uuid4())],
            }
        )
    )

    mock_handler_in_functions_rpc_interface(
        "list_function_job_collections",
        (
            [mock_registered_function_job_collection for _ in range(5)],
            PageMetaInfoLimitOffset(total=5, count=5, limit=10, offset=0),
        ),
    )

    response = await client.get(f"{API_VTAG}/function_job_collections")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["items"]
    assert len(data) == 5
    assert (
        RegisteredFunctionJobCollection.model_validate(data[0])
        == mock_registered_function_job_collection
    )


async def test_delete_function_job_collection(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function_job_collection: RegisteredFunctionJobCollection,
) -> None:

    mock_handler_in_functions_rpc_interface("delete_function_job_collection", None)

    # Now, delete the function job collection
    response = await client.delete(
        f"{API_VTAG}/function_job_collections/{mock_registered_function_job_collection.uid}"
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data is None


async def test_get_function_job_collection_jobs(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function_job_collection: RegisteredFunctionJobCollection,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "get_function_job_collection", mock_registered_function_job_collection
    )

    response = await client.get(
        f"{API_VTAG}/function_job_collections/{mock_registered_function_job_collection.uid}/function_jobs"
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == len(mock_registered_function_job_collection.job_ids)


async def test_list_function_job_collections_with_function_filter(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function_job_collection: RegisteredFunctionJobCollection,
    mock_registered_function: RegisteredProjectFunction,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "list_function_job_collections",
        (
            [mock_registered_function_job_collection for _ in range(2)],
            PageMetaInfoLimitOffset(total=5, count=2, limit=2, offset=1),
        ),
    )

    response = await client.get(
        f"{API_VTAG}/function_job_collections?function_id={mock_registered_function.uid}&limit=2&offset=1"
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 1
    assert len(data["items"]) == 2
    assert (
        RegisteredFunctionJobCollection.model_validate(data["items"][0])
        == mock_registered_function_job_collection
    )
