# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


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
    RegisteredProjectFunctionGet,
)
from models_library.api_schemas_webserver.users import MyFunctionPermissionsGet
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole

pytest_simcore_core_services_selection = ["rabbit"]


@pytest.fixture
def mock_function() -> dict[str, Any]:
    return {
        "title": "Test Function",
        "description": "A test function",
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
        "projectId": str(uuid4()),
        "functionClass": FunctionClass.PROJECT,
        "defaultInputs": None,
    }


@pytest.mark.parametrize(
    "user_role,add_user_function_api_access_rights,expected_register,expected_get,expected_delete,expected_get2",
    [
        (
            UserRole.USER,
            True,
            status.HTTP_201_CREATED,
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
        ),
    ],
    indirect=["add_user_function_api_access_rights"],
)
async def test_register_get_delete_function(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_function: dict[str, Any],
    expected_register: HTTPStatus,
    expected_get: HTTPStatus,
    expected_delete: HTTPStatus,
    expected_get2: HTTPStatus,
    add_user_function_api_access_rights: AsyncIterator[None],
    request: pytest.FixtureRequest,
) -> None:
    url = client.app.router["register_function"].url_for()
    response = await client.post(url, json=mock_function)
    data, error = await assert_status(response, expected_status_code=expected_register)
    if error:
        returned_function_uid = uuid4()
    else:
        returned_function = RegisteredProjectFunctionGet.model_validate(data)
        assert returned_function.uid is not None
        returned_function_uid = returned_function.uid

    url = client.app.router["get_function"].url_for(
        function_id=str(returned_function_uid)
    )
    response = await client.get(url)
    data, error = await assert_status(response, expected_get)
    if not error:
        retrieved_function = RegisteredProjectFunctionGet.model_validate(data)
        assert retrieved_function.uid == returned_function.uid

    url = client.app.router["delete_function"].url_for(
        function_id=str(returned_function_uid)
    )
    response = await client.delete(url)
    data, error = await assert_status(response, expected_delete)

    url = client.app.router["get_function"].url_for(
        function_id=str(returned_function_uid)
    )
    response = await client.get(url)
    data, error = await assert_status(response, expected_get2)


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize("expected_write_functions", [True, False])
async def test_list_user_functions_permissions(
    client: TestClient,
    logged_user: UserInfoDict,
    expected_write_functions: bool,
    logged_user_function_api_access_rights: dict[str, Any],
):
    assert (
        logged_user_function_api_access_rights["write_functions"]
        == expected_write_functions
    )

    url = client.app.router["list_user_functions_permissions"].url_for()
    response = await client.get(url)
    data, error = await assert_status(response, expected_status_code=status.HTTP_200_OK)

    assert not error
    function_permissions = MyFunctionPermissionsGet.model_validate(data)
    assert function_permissions.write_functions == expected_write_functions
