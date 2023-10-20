from pathlib import Path
from typing import Any, Callable
from uuid import UUID

import httpx
import pytest
import respx
from faker import Faker
from httpx import AsyncClient
from models_library.api_schemas_webserver.resource_usage import PricingUnitGet
from pydantic import parse_obj_as
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.jobs import Job
from simcore_service_api_server.models.schemas.solvers import Solver
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


@pytest.mark.parametrize(
    "capture_file",
    [
        "get_job_pricing_unit_invalid_job.json",
        "get_job_pricing_unit_invalid_solver.json",
        "get_job_pricing_unit_success.json",
    ],
)
async def test_get_solver_job_pricing_unit(
    client: AsyncClient,
    mocked_webserver_service_api_base,
    respx_mock_from_capture: Callable[
        [respx.MockRouter, Path, list[SideEffectCallback] | None], respx.MockRouter
    ],
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
    capture_file: str,
):
    solver_key: str = "simcore/services/comp/my_super_hpc_solver"
    solver_version: str = "3.14.0"
    job_id: UUID = UUID("87643648-3a38-44e2-9cfe-d86ab3d50629")

    def _get_job_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        response = capture.response_body
        assert isinstance(response, dict)
        if data := response.get("data"):
            assert isinstance(data, dict)
            assert data.get("uuid")
            data["uuid"] = path_params["project_id"]
            assert data.get("name")
            if capture_file != "get_job_pricing_unit_invalid_solver.json":
                data["name"] = Job.compose_resource_name(
                    parent_name=Solver.compose_resource_name(solver_key, solver_version),  # type: ignore
                    job_id=job_id,
                )
            response["data"] = data
        return response

    def _get_pricing_unit_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        return capture.response_body

    respx_mock = respx_mock_from_capture(
        mocked_webserver_service_api_base,
        project_tests_dir / "mocks" / capture_file,
        [_get_job_side_effect, _get_pricing_unit_side_effect]
        if capture_file == "get_job_pricing_unit_success.json"
        else [_get_job_side_effect],
    )

    response = await client.get(
        f"{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs/{job_id}/pricing_unit",
        auth=auth,
    )
    if capture_file == "get_job_pricing_unit_success.json":
        assert response.status_code == 200
        _ = parse_obj_as(PricingUnitGet, response.json())
    elif capture_file == "get_job_pricing_unit_invalid_job.json":
        assert response.status_code == 404
    elif capture_file == "get_job_pricing_unit_invalid_solver.json":
        assert response.status_code == 422
    else:
        pytest.fail()


async def test_get_solver_job_pricing_unit_with_payment(
    client: AsyncClient,
    mocked_webserver_service_api_base,
    mocked_directorv2_service_api_base,
    respx_mock_from_capture: Callable[
        [list[respx.MockRouter], Path, list[SideEffectCallback] | None],
        list[respx.MockRouter],
    ],
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
    faker: Faker,
):
    _solver_key: str = "simcore/services/comp/isolve"
    _version: str = "2.1.24"
    _job_id: str = "6e52228c-6edd-4505-9131-e901fdad5b17"
    _pricing_plan_id: int = faker.pyint(min_value=1)
    _pricing_unit_id: int = faker.pyint(min_value=1)

    def _get_job_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        response: dict[str, str] = capture.response_body  # type: ignore
        data = response.get("data")
        assert isinstance(data, dict)
        data["name"] = Job.compose_resource_name(
            parent_name=Solver.compose_resource_name(_solver_key, _version),  # type: ignore
            job_id=UUID(_job_id),
        )
        data["uuid"] = _job_id
        response["data"] = data
        return response

    def _put_pricing_plan_and_unit_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        _put_pricing_plan_and_unit_side_effect.was_called = True
        assert int(path_params["pricing_plan_id"]) == _pricing_plan_id
        assert int(path_params["pricing_unit_id"]) == _pricing_unit_id
        return capture.response_body

    def _start_job_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        response = capture.response_body
        assert isinstance(response, dict)
        response["id"] = _job_id
        return response

    _put_pricing_plan_and_unit_side_effect.was_called = False
    respx_mock = respx_mock_from_capture(
        [mocked_webserver_service_api_base] * 2 + [mocked_directorv2_service_api_base],
        project_tests_dir / "mocks" / "start_job_with_payment.json",
        [
            _get_job_side_effect,
            _put_pricing_plan_and_unit_side_effect,
            _start_job_side_effect,
        ],
    )

    response = await client.post(
        f"{API_VTAG}/solvers/{_solver_key}/releases/{_version}/jobs/{_job_id}:start",
        auth=auth,
        headers={
            "x-pricing-plan": f"{_pricing_plan_id}",
            "x-pricing-unit": f"{_pricing_unit_id}",
        },
    )
    assert response.status_code == 200
    assert _put_pricing_plan_and_unit_side_effect.was_called
