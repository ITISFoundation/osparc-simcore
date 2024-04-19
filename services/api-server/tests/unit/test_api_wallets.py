from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi import status
from httpx import AsyncClient
from models_library.api_schemas_webserver.wallets import WalletGetWithAvailableCredits
from pydantic import parse_obj_as
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.utils.http_calls_capture import HttpApiCallCaptureModel
from unit.conftest import SideEffectCallback

# pylint: disable=unused-argument
# pylint: disable=unused-variable


@pytest.mark.parametrize(
    "capture", ["get_wallet_success.json", "get_wallet_failure.json"]
)
async def test_get_wallet(
    client: AsyncClient,
    mocked_webserver_service_api_base,
    respx_mock_from_capture: Callable[
        [list[respx.MockRouter], Path, list[SideEffectCallback] | None],
        list[respx.MockRouter],
    ],
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

    respx_mock_from_capture(
        [mocked_webserver_service_api_base],
        project_tests_dir / "mocks" / capture,
        [_get_wallet_side_effect],
    )

    wallet_id: int = 159873
    response = await client.get(f"{API_VTAG}/wallets/{wallet_id}", auth=auth)
    if "success" in capture:
        assert response.status_code == 200
        wallet: WalletGetWithAvailableCredits = parse_obj_as(
            WalletGetWithAvailableCredits, response.json()
        )
        assert wallet.wallet_id == wallet_id
    elif "failure" in capture:
        assert response.status_code == 403
        assert response.json().get("errors") is not None


async def test_get_default_wallet(
    client: AsyncClient,
    mocked_webserver_service_api_base,
    respx_mock_from_capture: Callable[
        [list[respx.MockRouter], Path, list[SideEffectCallback]],
        list[respx.MockRouter],
    ],
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
):

    respx_mock_from_capture(
        [mocked_webserver_service_api_base],
        project_tests_dir / "mocks" / "get_default_wallet.json",
        [],
    )

    response = await client.get(f"{API_VTAG}/wallets/default", auth=auth)
    assert response.status_code == status.HTTP_200_OK
    _ = parse_obj_as(WalletGetWithAvailableCredits, response.json())
