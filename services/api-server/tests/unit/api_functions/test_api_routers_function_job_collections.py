# pylint: disable=unused-argument
import datetime
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import httpx
import pytest
from httpx import AsyncClient
from models_library.api_schemas_webserver.functions import (
    RegisteredFunctionJobCollection,
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
)
from models_library.rest_pagination import PageMetaInfoLimitOffset
from pytest_mock import MockerFixture
from servicelib.aiohttp import status
from simcore_service_api_server._meta import API_VTAG


async def test_get_function_job_collection(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    auth: httpx.BasicAuth,
) -> None:
    mock_registered_function_job_collection = (
        RegisteredFunctionJobCollection.model_validate(
            {
                "uid": str(uuid4()),
                "title": "Test Collection",
                "description": "A test function job collection",
                "job_ids": [str(uuid4()), str(uuid4())],
                "created_at": datetime.datetime.now(datetime.UTC),
            }
        )
    )

    mock_handler_in_functions_rpc_interface(
        "get_function_job_collection", mock_registered_function_job_collection
    )

    response = await client.get(
        f"{API_VTAG}/function_job_collections/{mock_registered_function_job_collection.uid}",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    assert (
        RegisteredFunctionJobCollection.model_validate(response.json())
        == mock_registered_function_job_collection
    )


async def test_list_function_job_collections(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    auth: httpx.BasicAuth,
) -> None:
    mock_registered_function_job_collection = (
        RegisteredFunctionJobCollection.model_validate(
            {
                "uid": str(uuid4()),
                "title": "Test Collection",
                "description": "A test function job collection",
                "job_ids": [str(uuid4()), str(uuid4())],
                "created_at": datetime.datetime.now(datetime.UTC),
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

    response = await client.get(f"{API_VTAG}/function_job_collections", auth=auth)
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
    fake_registered_function_job_collection: RegisteredFunctionJobCollection,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface("delete_function_job_collection", None)

    # Now, delete the function job collection
    response = await client.delete(
        f"{API_VTAG}/function_job_collections/{fake_registered_function_job_collection.uid}",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data is None


@pytest.mark.parametrize("response_type", ["page", "list"])
async def test_get_function_job_collection_jobs(
    client: AsyncClient,
    mock_rabbitmq_rpc_client: MockerFixture,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    fake_registered_function_job_collection: RegisteredFunctionJobCollection,
    fake_registered_project_function_job: RegisteredProjectFunctionJob,
    auth: httpx.BasicAuth,
    response_type: str | None,
) -> None:
    mock_handler_in_functions_rpc_interface(
        "list_function_jobs",
        (
            [fake_registered_project_function_job for _ in range(5)],
            PageMetaInfoLimitOffset(total=5, count=5, limit=10, offset=0),
        ),
    )
    query = {"limit": 10, "offset": 0} if response_type == "page" else None
    response = await client.get(
        f"{API_VTAG}/function_job_collections/{fake_registered_function_job_collection.uid}/function_jobs{'/page' if response_type == 'page' else ''}",
        params=query,
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    if response_type == "list":
        assert isinstance(data, list)
        assert len(data) == 5
    elif response_type == "page":
        assert isinstance(data, dict)
        assert data["total"] == 5
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert len(data["items"]) == 5


async def test_list_function_job_collections_with_function_filter(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    fake_registered_function_job_collection: RegisteredFunctionJobCollection,
    fake_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "list_function_job_collections",
        (
            [fake_registered_function_job_collection for _ in range(2)],
            PageMetaInfoLimitOffset(total=5, count=2, limit=2, offset=1),
        ),
    )

    response = await client.get(
        f"{API_VTAG}/function_job_collections?function_id={fake_registered_project_function.uid}&limit=2&offset=1",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 1
    assert len(data["items"]) == 2
    assert (
        RegisteredFunctionJobCollection.model_validate(data["items"][0])
        == fake_registered_function_job_collection
    )
