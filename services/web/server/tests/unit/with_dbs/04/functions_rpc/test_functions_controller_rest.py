# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


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
from servicelib.aiohttp import status
from simcore_service_webserver._meta import API_VTAG


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


async def test_register_function(
    client: TestClient,
    mock_function: dict[str, Any],
) -> None:
    response = await client.post(
        f"/{API_VTAG}/functions",
        json=mock_function,
    )
    assert response.status == status.HTTP_200_OK
    data = await response.json()
    returned_function = RegisteredProjectFunctionGet.model_validate(data.get("data"))
    assert returned_function.uid is not None


async def test_get_function(
    client: TestClient,
    mock_function: dict[str, Any],
):
    response = await client.post(
        f"/{API_VTAG}/functions",
        json=mock_function,
    )
    assert response.status == status.HTTP_200_OK
    data = await response.json()
    returned_function = RegisteredProjectFunctionGet.model_validate(data.get("data"))
    assert returned_function.uid is not None

    response = await client.get(
        f"/{API_VTAG}/functions/{returned_function.uid}",
    )
    assert response.status == status.HTTP_200_OK
    data = await response.json()
    retrieved_function = RegisteredProjectFunctionGet.model_validate(data.get("data"))
    assert retrieved_function.uid == returned_function.uid


async def test_delete_function(
    client: TestClient,
    mock_function: dict[str, Any],
):
    response = await client.post(
        f"/{API_VTAG}/functions",
        json=mock_function,
    )
    assert response.status == status.HTTP_200_OK
    data = await response.json()
    returned_function = RegisteredProjectFunctionGet.model_validate(data.get("data"))
    assert returned_function.uid is not None

    response = await client.delete(
        f"/{API_VTAG}/functions/{returned_function.uid}",
    )
    assert response.status == status.HTTP_204_NO_CONTENT

    response = await client.get(
        f"/{API_VTAG}/functions/{returned_function.uid}",
    )
    assert response.status == status.HTTP_404_NOT_FOUND
