# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements

from collections.abc import AsyncIterator
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

import pytest
from aiohttp.test_utils import TestClient
from common_library.json_serialization import json_dumps
from models_library.api_schemas_webserver.functions import (
    FunctionClass,
    JSONFunctionInputSchema,
    JSONFunctionOutputSchema,
    RegisteredFunctionGet,
)
from models_library.api_schemas_webserver.users import MyFunctionPermissionsGet
from pydantic import TypeAdapter
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole

pytest_simcore_core_services_selection = ["rabbit"]


async def _list_functions_and_validate(
    client: TestClient,
    expected_status: HTTPStatus,
    expected_count: int | None = None,
    params: dict[str, Any] | None = None,
    expected_uid_in_results: str | None = None,
    expected_uid_at_index: tuple[str, int] | None = None,
) -> list[RegisteredFunctionGet] | None:
    """Helper function to list functions and validate the response."""
    url = client.app.router["list_functions"].url_for()
    response = await client.get(url, params=params or {})
    data, error = await assert_status(response, expected_status)

    if error:
        return None

    retrieved_functions = TypeAdapter(list[RegisteredFunctionGet]).validate_python(data)

    if expected_count is not None:
        assert len(retrieved_functions) == expected_count

    if expected_uid_in_results is not None:
        assert expected_uid_in_results in [f"{f.uid}" for f in retrieved_functions]

    if expected_uid_at_index is not None:
        expected_uid, index = expected_uid_at_index
        assert f"{retrieved_functions[index].uid}" == expected_uid

    return retrieved_functions


@pytest.fixture(params=[FunctionClass.PROJECT, FunctionClass.SOLVER])
def mocked_function(request) -> dict[str, Any]:
    function_dict = {
        "title": f"Test {request.param} Function",
        "description": f"A test {request.param} function",
        "inputSchema": JSONFunctionInputSchema(
            schema_content={
                "type": "object",
                "properties": {"input1": {"type": "string"}},
            },
        ).model_dump(mode="json"),
        "outputSchema": JSONFunctionOutputSchema(
            schema_content={
                "type": "object",
                "properties": {"output1": {"type": "string"}},
            },
        ).model_dump(mode="json"),
        "functionClass": request.param,
        "defaultInputs": None,
    }

    match request.param:
        case FunctionClass.PROJECT:
            function_dict["projectId"] = f"{uuid4()}"
        case FunctionClass.SOLVER:
            function_dict["solverKey"] = "simcore/services/dynamic/test"
            function_dict["solverVersion"] = "1.0.0"

    return function_dict


@pytest.mark.parametrize(
    "user_role,add_user_function_api_access_rights,expected_register,expected_get,expected_list,expected_update,expected_delete,expected_get2",
    [
        (
            UserRole.USER,
            True,
            status.HTTP_201_CREATED,
            status.HTTP_200_OK,
            status.HTTP_200_OK,
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
            status.HTTP_404_NOT_FOUND,
        ),
        (
            UserRole.GUEST,
            False,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_403_FORBIDDEN,
        ),
    ],
    indirect=["add_user_function_api_access_rights"],
)
async def test_function_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    mocked_function: dict[str, Any],
    expected_register: HTTPStatus,
    expected_get: HTTPStatus,
    expected_list: HTTPStatus,
    expected_update: HTTPStatus,
    expected_delete: HTTPStatus,
    expected_get2: HTTPStatus,
    add_user_function_api_access_rights: AsyncIterator[None],
    request: pytest.FixtureRequest,
) -> None:
    # Register a new function
    url = client.app.router["register_function"].url_for()
    response = await client.post(url, json=mocked_function)
    data, error = await assert_status(response, expected_status_code=expected_register)
    if error:
        returned_function_uid = uuid4()
    else:
        returned_function = TypeAdapter(RegisteredFunctionGet).validate_python(data)
        assert returned_function.uid is not None
        returned_function_uid = returned_function.uid

    # Register a new function (duplicate)
    url = client.app.router["register_function"].url_for()
    mocked_function.update(title=mocked_function["title"] + " (duplicate)")
    response = await client.post(url, json=mocked_function)
    await assert_status(response, expected_status_code=expected_register)

    # Get the registered function
    url = client.app.router["get_function"].url_for(function_id=f"{returned_function_uid}")
    response = await client.get(url)
    data, error = await assert_status(response, expected_get)
    if not error:
        retrieved_function = TypeAdapter(RegisteredFunctionGet).validate_python(data)
        assert retrieved_function.uid == returned_function.uid

    # List existing functions (default)
    await _list_functions_and_validate(
        client,
        expected_list,
        expected_count=2,
        expected_uid_in_results=f"{returned_function_uid}",
        expected_uid_at_index=(
            f"{returned_function_uid}",
            1,
        ),  # ordered by modified_at by default
    )

    # List existing functions (ordered by created_at ascending)
    await _list_functions_and_validate(
        client,
        expected_list,
        expected_count=2,
        params={"order_by": json_dumps({"field": "created_at", "direction": "asc"})},
        expected_uid_in_results=f"{returned_function_uid}",
        expected_uid_at_index=(f"{returned_function_uid}", 0),
    )

    # List existing functions (searching for not existing)
    await _list_functions_and_validate(
        client,
        expected_list,
        expected_count=0,
        params={"search": "you_can_not_find_me_because_I_do_not_exist"},
    )

    # List existing functions (searching for duplicate)
    await _list_functions_and_validate(
        client,
        expected_list,
        expected_count=1,
        params={"search": "duplicate"},
    )

    # List existing functions (searching by title)
    await _list_functions_and_validate(
        client,
        expected_list,
        expected_count=1,
        params={"filters": json_dumps({"search_by_title": "duplicate"})},
    )

    # Set group permissions for other user
    new_group_id = other_logged_user["primary_gid"]
    new_group_access_rights = {"read": True, "write": True, "execute": False}

    url = client.app.router["create_or_update_function_group"].url_for(
        function_id=f"{returned_function_uid}", group_id=f"{new_group_id}"
    )

    response = await client.put(url, json=new_group_access_rights)
    data, error = await assert_status(response, expected_update)
    if not error:
        assert data == new_group_access_rights

    # Remove group permissions for original user
    url = client.app.router["delete_function_group"].url_for(
        function_id=f"{returned_function_uid}", group_id=f"{logged_user['primary_gid']}"
    )

    response = await client.delete(url)
    data, error = await assert_status(response, expected_delete)
    if not error:
        assert data is None

    # Check that original user no longer has access
    url = client.app.router["get_function"].url_for(function_id=f"{returned_function_uid}")
    response = await client.get(url)
    data, error = await assert_status(response, expected_get)
    if not error:
        retrieved_function = TypeAdapter(RegisteredFunctionGet).validate_python(data).model_dump()
        assert retrieved_function["access_rights"] == {new_group_id: new_group_access_rights}

    # Update existing function
    new_title = "Test Function (edited)"
    new_description = "A test function (edited)"
    url = client.app.router["update_function"].url_for(function_id=f"{returned_function_uid}")
    response = await client.patch(url, json={"title": new_title, "description": new_description})
    data, error = await assert_status(response, expected_update)
    if not error:
        updated_group_access_rights = TypeAdapter(RegisteredFunctionGet).validate_python(data)
        assert updated_group_access_rights.title == new_title
        assert updated_group_access_rights.description == new_description

    # Delete existing function
    url = client.app.router["delete_function"].url_for(function_id=f"{returned_function_uid}")
    response = await client.delete(url)
    data, error = await assert_status(response, expected_delete)

    # Check if the function was effectively deleted
    url = client.app.router["get_function"].url_for(function_id=f"{returned_function_uid}")
    response = await client.get(url)
    data, error = await assert_status(response, expected_get2)


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize(
    "expected_read_functions,expected_write_functions",
    [
        (True, True),
        (True, False),
        (False, True),  # Weird, but allowed for testing purposes
        (False, False),
    ],
)
async def test_list_user_functions_permissions(
    client: TestClient,
    logged_user: UserInfoDict,
    expected_read_functions: bool,
    expected_write_functions: bool,
    logged_user_function_api_access_rights: dict[str, Any],
):
    assert logged_user_function_api_access_rights["read_functions"] == expected_read_functions
    assert logged_user_function_api_access_rights["write_functions"] == expected_write_functions

    url = client.app.router["list_user_functions_permissions"].url_for()
    response = await client.get(url)
    data, error = await assert_status(response, expected_status_code=status.HTTP_200_OK)

    assert not error
    function_permissions = MyFunctionPermissionsGet.model_validate(data)
    assert function_permissions.read_functions == expected_read_functions
    assert function_permissions.write_functions == expected_write_functions


@pytest.mark.parametrize(
    "user_role,expected_read_functions,expected_write_functions",
    [(UserRole.USER, True, True)],
)
async def test_delete_function_with_associated_jobs(
    client: TestClient,
    logged_user: UserInfoDict,
    fake_function_with_associated_job: UUID,
    logged_user_function_api_access_rights: dict[str, Any],
) -> None:
    function_id = fake_function_with_associated_job

    url = client.app.router["get_function"].url_for(function_id=f"{function_id}")
    response = await client.get(url)
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert not error
    function = TypeAdapter(RegisteredFunctionGet).validate_python(data)
    assert function.uid == function_id

    url = client.app.router["delete_function"].url_for(function_id=f"{function_id}")
    response = await client.delete(url)
    data, error = await assert_status(response, status.HTTP_409_CONFLICT)
    assert error is not None

    url = client.app.router["get_function"].url_for(function_id=f"{function_id}")
    response = await client.get(url)
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert not error

    url = client.app.router["delete_function"].url_for(function_id=f"{function_id}")
    response = await client.delete(url, params={"force": "true"})
    data, error = await assert_status(response, status.HTTP_204_NO_CONTENT)
    assert not error

    url = client.app.router["get_function"].url_for(function_id=f"{function_id}")
    response = await client.get(url)
    data, error = await assert_status(response, status.HTTP_404_NOT_FOUND)
    assert error is not None
