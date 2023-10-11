from pathlib import Path
from typing import Any, Callable
from uuid import UUID

import httpx
import pytest
import respx
from httpx import AsyncClient
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.utils.http_calls_capture import HttpApiCallCaptureModel
from unit.conftest import SideEffectCallback

# pylint: disable=unused-argument
# pylint: disable=unused-variable


@pytest.mark.parametrize(
    "capture", ["get_job_wallet_found.json", "get_job_wallet_not_found.json"]
)
async def test_get_solver_job_wallet(
    client: AsyncClient,
    mocked_webserver_service_api_base,
    respx_mock_from_capture: Callable[
        [respx.MockRouter, Path, list[SideEffectCallback] | None], respx.MockRouter
    ],
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
    capture: str,
):

    _wallet_id: int = 1826

    def _get_job_wallet_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        response = capture.response_body
        assert isinstance(response, dict)
        if data := response.get("data"):
            assert isinstance(data, dict)
            assert data.get("walletId")
            response["data"]["walletId"] = _wallet_id
        return response

    respx_mock = respx_mock_from_capture(
        mocked_webserver_service_api_base,
        project_tests_dir / "mocks" / capture,
        [_get_job_wallet_side_effect],
    )

    solver_key: str = "simcore/services/comp/my_super_hpc_solver"
    solver_version: str = "3.14.0"
    job_id: UUID = UUID("87643648-3a38-44e2-9cfe-d86ab3d50629")
    response = await client.get(
        f"{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs/{job_id}/wallet",
        auth=auth,
    )
    if capture == "get_job_wallet_found.json":
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, dict)
        assert _wallet_id == body.get("walletId")
    elif capture == "get_job_wallet_not_found.json":
        assert response.status_code == 404
        body = response.json()
        assert isinstance(body, dict)
        assert body.get("data") is None
        assert body.get("errors") is not None
    else:
        pytest.fail()
