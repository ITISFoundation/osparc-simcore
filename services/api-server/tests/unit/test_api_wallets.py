# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import status
from httpx import AsyncClient
from models_library.api_schemas_webserver.wallets import WalletGetWithAvailableCredits
from pytest_simcore.helpers.httpx_calls_capture_models import (
    CreateRespxMockCallback,
    HttpApiCallCaptureModel,
)
from simcore_service_api_server._meta import API_VTAG


@pytest.mark.parametrize(
    "capture", ["get_wallet_success.json", "get_wallet_failure.json"]
)
async def test_get_wallet(
    client: AsyncClient,
    mocked_webserver_service_api_base,
    create_respx_mock_from_capture: CreateRespxMockCallback,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
    capture: str,
):
    def _get_wallet_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        response = capture.response_body
        assert isinstance(response, dict)
        if data := response.get("data"):
            assert isinstance(data, dict)
            assert data.get("walletId")
            response["data"]["walletId"] = path_params["wallet_id"]
        return response

    create_respx_mock_from_capture(
        respx_mocks=[mocked_webserver_service_api_base],
        capture_path=project_tests_dir / "mocks" / capture,
        side_effects_callbacks=[_get_wallet_side_effect],
    )

    wallet_id: int = 159873
    response = await client.get(f"{API_VTAG}/wallets/{wallet_id}", auth=auth)
    if "success" in capture:
        assert response.status_code == 200
        wallet: WalletGetWithAvailableCredits = (
            WalletGetWithAvailableCredits.model_validate(response.json())
        )
        assert wallet.wallet_id == wallet_id
    elif "failure" in capture:
        assert response.status_code == 403
        assert response.json().get("errors") is not None


async def test_get_default_wallet(
    client: AsyncClient,
    mocked_webserver_service_api_base,
    create_respx_mock_from_capture: CreateRespxMockCallback,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
):

    create_respx_mock_from_capture(
        respx_mocks=[mocked_webserver_service_api_base],
        capture_path=project_tests_dir / "mocks" / "get_default_wallet.json",
        side_effects_callbacks=[],
    )

    response = await client.get(f"{API_VTAG}/wallets/default", auth=auth)
    assert response.status_code == status.HTTP_200_OK
    _ = WalletGetWithAvailableCredits.model_validate(response.json())
