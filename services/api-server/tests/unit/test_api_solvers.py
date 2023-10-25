from pathlib import Path
from typing import Callable

import httpx
import pytest
import respx
from httpx import AsyncClient
from models_library.api_schemas_webserver.resource_usage import ServicePricingPlanGet
from pydantic import parse_obj_as
from simcore_service_api_server._meta import API_VTAG
from unit.conftest import SideEffectCallback


@pytest.mark.parametrize(
    "capture,expected_status_code",
    [
        ("get_solver_pricing_plan_invalid_solver.json", 503),
        ("get_solver_pricing_plan_success.json", 200),
    ],
)
async def test_get_solver_pricing_plan(
    client: AsyncClient,
    mocked_webserver_service_api_base,
    respx_mock_from_capture: Callable[
        [list[respx.MockRouter], Path, list[SideEffectCallback] | None],
        list[respx.MockRouter],
    ],
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
    capture: str,
    expected_status_code: int,
):

    respx_mock = respx_mock_from_capture(
        [mocked_webserver_service_api_base], project_tests_dir / "mocks" / capture, []
    )
    assert respx_mock

    _my_solver: str = "simcore/services/comp/my_solver"
    _version: str = "2.4.3"
    response = await client.get(
        f"{API_VTAG}/solvers/{_my_solver}/releases/{_version}/pricing_plan",
        auth=auth,
    )
    assert expected_status_code == response.status_code
    if response.status_code == 200:
        _ = parse_obj_as(ServicePricingPlanGet, response.json())
