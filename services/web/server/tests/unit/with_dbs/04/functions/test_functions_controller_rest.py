# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import json
from collections.abc import AsyncIterator
from http import HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
from aiohttp.test_utils import TestClient
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
    url = client.app.router["get_function"].url_for(
        function_id=f"{returned_function_uid}"
    )
    response = await client.get(url)
    data, error = await assert_status(response, expected_get)
    if not error:
        retrieved_function = TypeAdapter(RegisteredFunctionGet).validate_python(data)
        assert retrieved_function.uid == returned_function.uid

    # List existing functions (default)
    url = client.app.router["list_functions"].url_for()
    response = await client.get(url)
    data, error = await assert_status(response, expected_list)
    if not error:
        retrieved_functions = TypeAdapter(list[RegisteredFunctionGet]).validate_python(
            data
        )
        assert len(retrieved_functions) == 2
        assert returned_function_uid in [f.uid for f in retrieved_functions]
        assert (
            retrieved_functions[1].uid == returned_function_uid
        )  # ordered by modified_at by default

    # List existing functions (ordered by created_at ascending)
    url = client.app.router["list_functions"].url_for()
    response = await client.get(
        url,
        params={"order_by": json.dumps({"field": "created_at", "direction": "asc"})},
    )
    data, error = await assert_status(response, expected_list)
    if not error:
        retrieved_functions = TypeAdapter(list[RegisteredFunctionGet]).validate_python(
            data
        )
        assert len(retrieved_functions) == 2
        assert returned_function_uid in [f.uid for f in retrieved_functions]
        assert retrieved_functions[0].uid == returned_function_uid

    # List existing functions (searching for not existing)
    url = client.app.router["list_functions"].url_for()
    response = await client.get(
        url, params={"search": "you_can_not_find_me_because_I_do_not_exist"}
    )
    data, error = await assert_status(response, expected_list)
    if not error:
        retrieved_functions = TypeAdapter(list[RegisteredFunctionGet]).validate_python(
            data
        )
        assert len(retrieved_functions) == 0

    # List existing functions (searching for duplicate)
    url = client.app.router["list_functions"].url_for()
    response = await client.get(url, params={"search": "duplicate"})
    data, error = await assert_status(response, expected_list)
    if not error:
        retrieved_functions = TypeAdapter(list[RegisteredFunctionGet]).validate_python(
            data
        )
        assert len(retrieved_functions) == 1

    # List existing functions (searching by title)
    url = client.app.router["list_functions"].url_for()
    response = await client.get(
        url, params={"filters": json.dumps({"search_by_title": "duplicate"})}
    )
    data, error = await assert_status(response, expected_list)
    if not error:
        retrieved_functions = TypeAdapter(list[RegisteredFunctionGet]).validate_python(
            data
        )
        assert len(retrieved_functions) == 1

    # Update existing function
    new_title = "Test Function (edited)"
    new_description = "A test function (edited)"
    url = client.app.router["update_function"].url_for(
        function_id=f"{returned_function_uid}"
    )
    response = await client.patch(
        url, json={"title": new_title, "description": new_description}
    )
    data, error = await assert_status(response, expected_update)
    if not error:
        updated_function = TypeAdapter(RegisteredFunctionGet).validate_python(data)
        assert updated_function.title == new_title
        assert updated_function.description == new_description

    # Delete existing function
    url = client.app.router["delete_function"].url_for(
        function_id=f"{returned_function_uid}"
    )
    response = await client.delete(url)
    data, error = await assert_status(response, expected_delete)

    # Check if the function was effectively deleted
    url = client.app.router["get_function"].url_for(
        function_id=f"{returned_function_uid}"
    )
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
    assert (
        logged_user_function_api_access_rights["read_functions"]
        == expected_read_functions
    )
    assert (
        logged_user_function_api_access_rights["write_functions"]
        == expected_write_functions
    )

    url = client.app.router["list_user_functions_permissions"].url_for()
    response = await client.get(url)
    data, error = await assert_status(response, expected_status_code=status.HTTP_200_OK)

    assert not error
    function_permissions = MyFunctionPermissionsGet.model_validate(data)
    assert function_permissions.read_functions == expected_read_functions
    assert function_permissions.write_functions == expected_write_functions
