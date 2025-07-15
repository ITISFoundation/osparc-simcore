# pylint: disable=unused-argument
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=redefined-outer-name

import datetime
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import httpx
import pytest
import respx
from faker import Faker
from httpx import AsyncClient
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.api_schemas_webserver.functions import (
    FunctionJobCollection,
    ProjectFunction,
    ProjectFunctionJob,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
)
from models_library.functions import (
    FunctionUserAccessRights,
    FunctionUserApiAccessRights,
    RegisteredFunctionJob,
)
from models_library.functions_errors import (
    FunctionIDNotFoundError,
    FunctionReadAccessDeniedError,
)
from models_library.rest_pagination import PageMetaInfoLimitOffset
from models_library.users import UserID
from pytest_mock import MockType
from pytest_simcore.helpers.httpx_calls_capture_models import HttpApiCallCaptureModel
from servicelib.aiohttp import status
from servicelib.common_headers import (
    X_SIMCORE_PARENT_NODE_ID,
    X_SIMCORE_PARENT_PROJECT_UUID,
)
from simcore_service_api_server._meta import API_VTAG

_faker = Faker()


async def test_register_function(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_function: ProjectFunction,
    auth: httpx.BasicAuth,
    mock_registered_project_function: RegisteredProjectFunction,
) -> None:
    mock_handler_in_functions_rpc_interface(
        "register_function", mock_registered_project_function
    )
    response = await client.post(
        f"{API_VTAG}/functions", json=mock_function.model_dump(mode="json"), auth=auth
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    returned_function = RegisteredProjectFunction.model_validate(data)
    assert returned_function.uid is not None
    assert returned_function == mock_registered_project_function


async def test_register_function_invalid(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    auth: httpx.BasicAuth,
) -> None:
    invalid_function = {
        "title": "test_function",
        "function_class": "invalid_class",  # Invalid class
        "project_id": str(uuid4()),
    }
    response = await client.post(
        f"{API_VTAG}/functions", json=invalid_function, auth=auth
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert (
        "Input tag 'invalid_class' found using 'function_class' does not"
        in response.json()["errors"][0]["msg"]
    )


async def test_get_function(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:
    function_id = str(uuid4())

    mock_handler_in_functions_rpc_interface(
        "get_function", mock_registered_project_function
    )
    response = await client.get(f"{API_VTAG}/functions/{function_id}", auth=auth)
    assert response.status_code == status.HTTP_200_OK
    returned_function = RegisteredProjectFunction.model_validate(response.json())
    assert returned_function == mock_registered_project_function


async def test_get_function_not_found(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[
        [str, Any, Exception | None], None
    ],
    auth: httpx.BasicAuth,
) -> None:
    non_existent_function_id = str(uuid4())

    mock_handler_in_functions_rpc_interface(
        "get_function",
        None,
        FunctionIDNotFoundError(function_id=non_existent_function_id),
    )
    response = await client.get(
        f"{API_VTAG}/functions/{non_existent_function_id}", auth=auth
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_get_function_read_access_denied(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[
        [str, Any, Exception | None], None
    ],
    mock_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:
    unauthorized_user_id = "unauthorized user"
    mock_handler_in_functions_rpc_interface(
        "get_function",
        None,
        FunctionReadAccessDeniedError(
            function_id=mock_registered_project_function.uid,
            user_id=unauthorized_user_id,
        ),
    )
    response = await client.get(
        f"{API_VTAG}/functions/{mock_registered_project_function.uid}", auth=auth
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["errors"][0] == (
        f"Function {mock_registered_project_function.uid} read access denied for user {unauthorized_user_id}"
    )


async def test_list_functions(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "list_functions",
        (
            [mock_registered_project_function for _ in range(5)],
            PageMetaInfoLimitOffset(total=5, count=5, limit=10, offset=0),
        ),
    )

    response = await client.get(
        f"{API_VTAG}/functions", params={"limit": 10, "offset": 0}, auth=auth
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["items"]
    assert len(data) == 5
    assert data[0]["title"] == mock_registered_project_function.title


async def test_update_function_title(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "update_function_title",
        RegisteredProjectFunction(
            **{
                **mock_registered_project_function.model_dump(),
                "title": "updated_example_function",
            }
        ),
    )

    # Update the function title
    updated_title = {"title": "updated_example_function"}
    response = await client.patch(
        f"{API_VTAG}/functions/{mock_registered_project_function.uid}/title",
        params=updated_title,
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["title"] == updated_title["title"]


async def test_update_function_description(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:
    mock_handler_in_functions_rpc_interface(
        "update_function_description",
        RegisteredProjectFunction(
            **{
                **mock_registered_project_function.model_dump(),
                "description": "updated_example_function",
            }
        ),
    )

    # Update the function description
    updated_description = {"description": "updated_example_function"}
    response = await client.patch(
        f"{API_VTAG}/functions/{mock_registered_project_function.uid}/description",
        params=updated_description,
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["description"] == updated_description["description"]


async def test_get_function_input_schema(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "get_function", mock_registered_project_function
    )

    response = await client.get(
        f"{API_VTAG}/functions/{mock_registered_project_function.uid}/input_schema",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert (
        data["schema_content"]
        == mock_registered_project_function.input_schema.schema_content
    )


async def test_get_function_output_schema(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "get_function", mock_registered_project_function
    )

    response = await client.get(
        f"{API_VTAG}/functions/{mock_registered_project_function.uid}/output_schema",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert (
        data["schema_content"]
        == mock_registered_project_function.output_schema.schema_content
    )


async def test_validate_function_inputs(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "get_function", mock_registered_project_function
    )

    # Validate inputs
    validate_payload = {"input1": 10}
    response = await client.post(
        f"{API_VTAG}/functions/{mock_registered_project_function.uid}:validate_inputs",
        json=validate_payload,
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data == [True, "Inputs are valid"]


async def test_delete_function(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:
    mock_handler_in_functions_rpc_interface("delete_function", None)

    # Delete the function
    response = await client.delete(
        f"{API_VTAG}/functions/{mock_registered_project_function.uid}", auth=auth
    )
    assert response.status_code == status.HTTP_200_OK


async def test_register_function_job(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_project_function_job: ProjectFunctionJob,
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    auth: httpx.BasicAuth,
) -> None:
    """Test the register_function_job endpoint."""

    mock_handler_in_functions_rpc_interface(
        "register_function_job", mock_registered_project_function_job
    )

    response = await client.post(
        f"{API_VTAG}/function_jobs",
        json=mock_project_function_job.model_dump(mode="json"),
        auth=auth,
    )

    assert response.status_code == status.HTTP_200_OK
    assert (
        RegisteredProjectFunctionJob.model_validate(response.json())
        == mock_registered_project_function_job
    )


async def test_get_function_job(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "get_function_job", mock_registered_project_function_job
    )

    # Now, get the function job
    response = await client.get(
        f"{API_VTAG}/function_jobs/{mock_registered_project_function_job.uid}",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    assert (
        RegisteredProjectFunctionJob.model_validate(response.json())
        == mock_registered_project_function_job
    )


async def test_list_function_jobs(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "list_function_jobs",
        (
            [mock_registered_project_function_job for _ in range(5)],
            PageMetaInfoLimitOffset(total=5, count=5, limit=10, offset=0),
        ),
    )

    # Now, list function jobs
    response = await client.get(f"{API_VTAG}/function_jobs", auth=auth)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["items"]
    assert len(data) == 5
    assert (
        RegisteredProjectFunctionJob.model_validate(data[0])
        == mock_registered_project_function_job
    )


async def test_list_function_jobs_with_function_filter(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    mock_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "list_function_jobs",
        (
            [mock_registered_project_function_job for _ in range(5)],
            PageMetaInfoLimitOffset(total=5, count=5, limit=10, offset=0),
        ),
    )

    # Now, list function jobs with a filter
    response = await client.get(
        f"{API_VTAG}/functions/{mock_registered_project_function.uid}/jobs", auth=auth
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()["items"]
    assert len(data) == 5
    assert (
        RegisteredProjectFunctionJob.model_validate(data[0])
        == mock_registered_project_function_job
    )


async def test_delete_function_job(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function_job: RegisteredProjectFunctionJob,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface("delete_function_job", None)

    # Now, delete the function job
    response = await client.delete(
        f"{API_VTAG}/function_jobs/{mock_registered_project_function_job.uid}",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK


async def test_register_function_job_collection(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    auth: httpx.BasicAuth,
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
                "created_at": datetime.datetime.now(datetime.UTC),
            }
        )
    )

    mock_handler_in_functions_rpc_interface(
        "register_function_job_collection", mock_registered_function_job_collection
    )

    response = await client.post(
        f"{API_VTAG}/function_job_collections",
        json=mock_function_job_collection.model_dump(mode="json"),
        auth=auth,
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
    mock_registered_function_job_collection: RegisteredFunctionJobCollection,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface("delete_function_job_collection", None)

    # Now, delete the function job collection
    response = await client.delete(
        f"{API_VTAG}/function_job_collections/{mock_registered_function_job_collection.uid}",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data is None


async def test_get_function_job_collection_jobs(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function_job_collection: RegisteredFunctionJobCollection,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "get_function_job_collection", mock_registered_function_job_collection
    )

    response = await client.get(
        f"{API_VTAG}/function_job_collections/{mock_registered_function_job_collection.uid}/function_jobs",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == len(mock_registered_function_job_collection.job_ids)


async def test_list_function_job_collections_with_function_filter(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_function_job_collection: RegisteredFunctionJobCollection,
    mock_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:

    mock_handler_in_functions_rpc_interface(
        "list_function_job_collections",
        (
            [mock_registered_function_job_collection for _ in range(2)],
            PageMetaInfoLimitOffset(total=5, count=2, limit=2, offset=1),
        ),
    )

    response = await client.get(
        f"{API_VTAG}/function_job_collections?function_id={mock_registered_project_function.uid}&limit=2&offset=1",
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
        == mock_registered_function_job_collection
    )


@pytest.mark.parametrize("user_has_execute_right", [False, True])
@pytest.mark.parametrize(
    "funcapi_endpoint,endpoint_inputs", [("run", {}), ("map", [{}, {}])]
)
async def test_run_map_function_not_allowed(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
    user_id: UserID,
    mocked_webserver_rest_api_base: respx.MockRouter,
    mocked_webserver_rpc_api: dict[str, MockType],
    user_has_execute_right: bool,
    funcapi_endpoint: str,
    endpoint_inputs: dict | list[dict],
) -> None:
    """Test that running a function is not allowed."""

    mock_handler_in_functions_rpc_interface(
        "get_function_user_permissions",
        FunctionUserAccessRights(
            user_id=user_id,
            execute=False,
            read=True,
            write=True,
        ),
    )
    mock_handler_in_functions_rpc_interface(
        "get_functions_user_api_access_rights",
        FunctionUserApiAccessRights(
            user_id=user_id,
            execute_functions=user_has_execute_right,
            write_functions=True,
            read_functions=True,
        ),
    )

    # Monkeypatching MagicMock because otherwise it refuse to be used in an await statement
    async def async_magic():
        pass

    MagicMock.__await__ = lambda _: async_magic().__await__()

    response = await client.post(
        f"{API_VTAG}/functions/{mock_registered_project_function.uid}:{funcapi_endpoint}",
        json=endpoint_inputs,
        auth=auth,
        headers={
            X_SIMCORE_PARENT_PROJECT_UUID: "null",
            X_SIMCORE_PARENT_NODE_ID: "null",
        },
    )
    if user_has_execute_right:
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["errors"][0] == (
            f"Function {mock_registered_project_function.uid} execute access denied for user {user_id}"
        )
    else:
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["errors"][0] == (
            f"User {user_id} does not have the permission to execute functions"
        )


@pytest.mark.parametrize(
    "parent_project_uuid, parent_node_uuid, expected_status_code",
    [
        (None, None, status.HTTP_422_UNPROCESSABLE_ENTITY),
        (f"{_faker.uuid4()}", None, status.HTTP_422_UNPROCESSABLE_ENTITY),
        (None, f"{_faker.uuid4()}", status.HTTP_422_UNPROCESSABLE_ENTITY),
        (f"{_faker.uuid4()}", f"{_faker.uuid4()}", status.HTTP_200_OK),
        ("null", "null", status.HTTP_200_OK),
    ],
)
@pytest.mark.parametrize("capture", ["run_study_function_parent_info.json"])
async def test_run_project_function_parent_info(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function: RegisteredProjectFunction,
    mock_registered_project_function_job: RegisteredFunctionJob,
    auth: httpx.BasicAuth,
    user_id: UserID,
    mocked_webserver_rest_api_base: respx.MockRouter,
    mocked_directorv2_rest_api_base: respx.MockRouter,
    mocked_webserver_rpc_api: dict[str, MockType],
    create_respx_mock_from_capture,
    project_tests_dir: Path,
    parent_project_uuid: str | None,
    parent_node_uuid: str | None,
    expected_status_code: int,
    capture: str,
) -> None:

    def _default_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        if request.method == "POST" and request.url.path.endswith("/projects"):
            if parent_project_uuid and parent_project_uuid != "null":
                _parent_uuid = request.headers.get(X_SIMCORE_PARENT_PROJECT_UUID)
                assert _parent_uuid is not None
                assert parent_project_uuid == _parent_uuid
            if parent_node_uuid and parent_node_uuid != "null":
                _parent_node_uuid = request.headers.get(X_SIMCORE_PARENT_NODE_ID)
                assert _parent_node_uuid is not None
                assert parent_node_uuid == _parent_node_uuid
        return capture.response_body

    create_respx_mock_from_capture(
        respx_mocks=[mocked_webserver_rest_api_base, mocked_directorv2_rest_api_base],
        capture_path=project_tests_dir / "mocks" / capture,
        side_effects_callbacks=[_default_side_effect] * 50,
    )

    mock_handler_in_functions_rpc_interface(
        "get_function_user_permissions",
        FunctionUserAccessRights(
            user_id=user_id,
            execute=True,
            read=True,
            write=True,
        ),
    )
    mock_handler_in_functions_rpc_interface(
        "get_function", mock_registered_project_function
    )
    mock_handler_in_functions_rpc_interface("find_cached_function_jobs", [])
    mock_handler_in_functions_rpc_interface(
        "register_function_job", mock_registered_project_function_job
    )
    mock_handler_in_functions_rpc_interface(
        "get_functions_user_api_access_rights",
        FunctionUserApiAccessRights(
            user_id=user_id,
            execute_functions=True,
            write_functions=True,
            read_functions=True,
        ),
    )

    headers = dict()
    if parent_project_uuid:
        headers[X_SIMCORE_PARENT_PROJECT_UUID] = parent_project_uuid
    if parent_node_uuid:
        headers[X_SIMCORE_PARENT_NODE_ID] = parent_node_uuid

    response = await client.post(
        f"{API_VTAG}/functions/{mock_registered_project_function.uid}:run",
        json={},
        auth=auth,
        headers=headers,
    )
    assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    "parent_project_uuid, parent_node_uuid, expected_status_code",
    [
        (None, None, status.HTTP_422_UNPROCESSABLE_ENTITY),
        (f"{_faker.uuid4()}", None, status.HTTP_422_UNPROCESSABLE_ENTITY),
        (None, f"{_faker.uuid4()}", status.HTTP_422_UNPROCESSABLE_ENTITY),
        (f"{_faker.uuid4()}", f"{_faker.uuid4()}", status.HTTP_200_OK),
        ("null", "null", status.HTTP_200_OK),
    ],
)
@pytest.mark.parametrize("capture", ["run_study_function_parent_info.json"])
async def test_map_function_parent_info(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function: RegisteredProjectFunction,
    mock_registered_project_function_job: RegisteredFunctionJob,
    auth: httpx.BasicAuth,
    user_id: UserID,
    mocked_webserver_rest_api_base: respx.MockRouter,
    mocked_directorv2_rest_api_base: respx.MockRouter,
    mocked_webserver_rpc_api: dict[str, MockType],
    create_respx_mock_from_capture,
    project_tests_dir: Path,
    parent_project_uuid: str | None,
    parent_node_uuid: str | None,
    expected_status_code: int,
    capture: str,
) -> None:

    side_effect_checks = dict()

    def _default_side_effect(
        side_effect_checks: dict,
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        if request.method == "POST" and request.url.path.endswith("/projects"):
            side_effect_checks["headers_checked"] = True
            if parent_project_uuid and parent_project_uuid != "null":
                _parent_uuid = request.headers.get(X_SIMCORE_PARENT_PROJECT_UUID)
                assert _parent_uuid is not None
                assert parent_project_uuid == _parent_uuid
            if parent_node_uuid and parent_node_uuid != "null":
                _parent_node_uuid = request.headers.get(X_SIMCORE_PARENT_NODE_ID)
                assert _parent_node_uuid is not None
                assert parent_node_uuid == _parent_node_uuid
        return capture.response_body

    create_respx_mock_from_capture(
        respx_mocks=[mocked_webserver_rest_api_base, mocked_directorv2_rest_api_base],
        capture_path=project_tests_dir / "mocks" / capture,
        side_effects_callbacks=[partial(_default_side_effect, side_effect_checks)] * 50,
    )

    mock_handler_in_functions_rpc_interface(
        "get_function_user_permissions",
        FunctionUserAccessRights(
            user_id=user_id,
            execute=True,
            read=True,
            write=True,
        ),
    )
    mock_handler_in_functions_rpc_interface(
        "get_function", mock_registered_project_function
    )
    mock_handler_in_functions_rpc_interface("find_cached_function_jobs", [])
    mock_handler_in_functions_rpc_interface(
        "register_function_job", mock_registered_project_function_job
    )
    mock_handler_in_functions_rpc_interface(
        "get_functions_user_api_access_rights",
        FunctionUserApiAccessRights(
            user_id=user_id,
            execute_functions=True,
            write_functions=True,
            read_functions=True,
        ),
    )
    mock_handler_in_functions_rpc_interface(
        "register_function_job_collection",
        RegisteredFunctionJobCollection(
            uid=UUID(_faker.uuid4()),
            title="Test Collection",
            description="A test function job collection",
            job_ids=[],
            created_at=datetime.datetime.now(datetime.UTC),
        ),
    )

    headers = dict()
    if parent_project_uuid:
        headers[X_SIMCORE_PARENT_PROJECT_UUID] = parent_project_uuid
    if parent_node_uuid:
        headers[X_SIMCORE_PARENT_NODE_ID] = parent_node_uuid

    response = await client.post(
        f"{API_VTAG}/functions/{mock_registered_project_function.uid}:map",
        json=[{}, {}],
        auth=auth,
        headers=headers,
    )
    if expected_status_code == status.HTTP_200_OK:
        assert side_effect_checks["headers_checked"] == True
    assert response.status_code == expected_status_code


async def test_export_logs_project_function_job(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function: RegisteredFunction,
    mock_registered_project_function_job: RegisteredFunctionJob,
    mocked_directorv2_rpc_api: dict[str, MockType],
    mocked_storage_rpc_api: dict[str, MockType],
    auth: httpx.BasicAuth,
    user_id: UserID,
):
    mock_handler_in_functions_rpc_interface(
        "get_function", mock_registered_project_function
    )
    mock_handler_in_functions_rpc_interface(
        "get_function_job", mock_registered_project_function_job
    )

    response = await client.post(
        f"{API_VTAG}/function_jobs/{mock_registered_project_function_job.uid}/log",
        auth=auth,
    )

    assert response.status_code == status.HTTP_200_OK
    TaskGet.model_validate(response.json())


async def test_export_logs_solver_function_job(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_solver_function: RegisteredFunction,
    mock_registered_solver_function_job: RegisteredFunctionJob,
    mocked_directorv2_rpc_api: dict[str, MockType],
    mocked_storage_rpc_api: dict[str, MockType],
    auth: httpx.BasicAuth,
    user_id: UserID,
):
    mock_handler_in_functions_rpc_interface(
        "get_function", mock_registered_solver_function
    )
    mock_handler_in_functions_rpc_interface(
        "get_function_job", mock_registered_solver_function_job
    )

    response = await client.post(
        f"{API_VTAG}/function_jobs/{mock_registered_solver_function_job.uid}/log",
        auth=auth,
    )

    assert response.status_code == status.HTTP_200_OK
    TaskGet.model_validate(response.json())
