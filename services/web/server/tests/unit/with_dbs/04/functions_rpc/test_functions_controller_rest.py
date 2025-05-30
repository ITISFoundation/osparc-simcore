# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


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
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole


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
    "user_role,expected_register,expected_get,expected_delete,expected_get2",
    [
        (
            UserRole.USER,
            status.HTTP_201_CREATED,
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
            status.HTTP_404_NOT_FOUND,
        ),
        (
            UserRole.GUEST,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_403_FORBIDDEN,
        ),
    ],
)
async def test_register_get_delete_function(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_function: dict[str, Any],
    expected_register: HTTPStatus,
    expected_get: HTTPStatus,
    expected_delete: HTTPStatus,
    expected_get2: HTTPStatus,
) -> None:
    assert client.app
    url = client.app.router["register_function"].url_for()
    response = await client.post(
        f"{url}",
        json=mock_function,
    )
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
    response = await client.get(
        f"{url}",
    )
    data, error = await assert_status(response, expected_get)
    if not error:
        retrieved_function = RegisteredProjectFunctionGet.model_validate(data)
        assert retrieved_function.uid == returned_function.uid

    url = client.app.router["delete_function"].url_for(
        function_id=str(returned_function_uid)
    )
    response = await client.delete(
        f"{url}",
    )
    data, error = await assert_status(response, expected_delete)

    url = client.app.router["get_function"].url_for(
        function_id=str(returned_function_uid)
    )
    response = await client.get(
        f"{url}",
    )
    data, error = await assert_status(response, expected_get2)
