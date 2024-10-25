# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from pathlib import Path

import httpx
import pytest
from fastapi import status
from httpx import AsyncClient
from models_library.api_schemas_api_server.pricing_plans import ServicePricingPlanGet
from pytest_simcore.helpers.httpx_calls_capture_models import CreateRespxMockCallback
from simcore_service_api_server._meta import API_VTAG


@pytest.mark.parametrize(
    "capture,expected_status_code",
    [
        (
            "get_solver_pricing_plan_invalid_solver.json",
            status.HTTP_502_BAD_GATEWAY,
        ),
        ("get_solver_pricing_plan_success.json", status.HTTP_200_OK),
    ],
)
async def test_get_solver_pricing_plan(
    client: AsyncClient,
    mocked_webserver_service_api_base,
    create_respx_mock_from_capture: CreateRespxMockCallback,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
    capture: str,
    expected_status_code: int,
):

    respx_mock = create_respx_mock_from_capture(
        respx_mocks=[mocked_webserver_service_api_base],
        capture_path=project_tests_dir / "mocks" / capture,
        side_effects_callbacks=[],
    )
    assert respx_mock

    _my_solver: str = "simcore/services/comp/my_solver"
    _version: str = "2.4.3"
    response = await client.get(
        f"{API_VTAG}/solvers/{_my_solver}/releases/{_version}/pricing_plan",
        auth=auth,
    )
    assert expected_status_code == response.status_code
    if response.status_code == status.HTTP_200_OK:
        _ = ServicePricingPlanGet.model_validate(response.json())
