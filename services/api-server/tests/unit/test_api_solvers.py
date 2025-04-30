# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from pathlib import Path

import httpx
import pytest
import respx
from fastapi import status
from httpx import AsyncClient
from models_library.api_schemas_api_server.pricing_plans import ServicePricingPlanGet
from pytest_mock import MockType
from pytest_simcore.helpers.catalog_rpc_server import ZeroListingCatalogRpcSideEffects
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
    mocked_webserver_rest_api_base: respx.MockRouter,
    create_respx_mock_from_capture: CreateRespxMockCallback,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
    capture: str,
    expected_status_code: int,
):

    respx_mock = create_respx_mock_from_capture(
        respx_mocks=[mocked_webserver_rest_api_base],
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


@pytest.mark.parametrize(
    "solver_key,expected_status_code",
    [
        ("simcore/services/comp/valid_solver", status.HTTP_200_OK),
    ],
)
async def test_get_latest_solver_release(
    client: AsyncClient,
    mocked_catalog_rpc_api: dict[str, MockType],
    auth: httpx.BasicAuth,
    solver_key: str,
    expected_status_code: int,
):
    response = await client.get(
        f"{API_VTAG}/solvers/{solver_key}/latest",
        auth=auth,
    )
    assert response.status_code == expected_status_code
    if response.status_code == status.HTTP_200_OK:
        assert "id" in response.json()
        assert response.json()["id"] == solver_key


@pytest.mark.parametrize(
    "catalog_rpc_side_effects",
    [ZeroListingCatalogRpcSideEffects()],
    indirect=True,
)
@pytest.mark.parametrize(
    "solver_key,expected_status_code",
    [
        ("simcore/services/comp/valid_solver", status.HTTP_404_NOT_FOUND),
    ],
)
async def test_get_latest_solver_release_zero_releases(
    client: AsyncClient,
    mocked_catalog_rpc_api,
    auth: httpx.BasicAuth,
    solver_key: str,
    expected_status_code: int,
):
    response = await client.get(
        f"{API_VTAG}/solvers/{solver_key}/latest",
        auth=auth,
    )
    assert response.status_code == expected_status_code
