from pathlib import Path

from fastapi import status
from httpx import AsyncClient, BasicAuth
from models_library.api_schemas_webserver.product import GetCreditPrice
from pytest_simcore.helpers.httpx_calls_capture_models import CreateRespxMockCallback
from simcore_service_api_server._meta import API_VTAG


async def test_get_credits_price(
    client: AsyncClient,
    auth: BasicAuth,
    mocked_webserver_service_api_base,
    create_respx_mock_from_capture: CreateRespxMockCallback,
    project_tests_dir: Path,
):

    create_respx_mock_from_capture(
        respx_mocks=[mocked_webserver_service_api_base],
        capture_path=project_tests_dir / "mocks" / "get_credits_price.json",
        side_effects_callbacks=[],
    )

    response = await client.get(f"{API_VTAG}/credits/price", auth=auth)
    assert response.status_code == status.HTTP_200_OK
    _ = GetCreditPrice.model_validate(response.json())
