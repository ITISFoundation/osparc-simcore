# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any, Final
from uuid import UUID

import httpx
import pytest
import respx
from faker import Faker
from fastapi import status
from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
from models_library.api_schemas_webserver.resource_usage import PricingUnitGet
from models_library.api_schemas_webserver.wallets import WalletGetWithAvailableCredits
from models_library.generics import Envelope
from pydantic import parse_obj_as
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.jobs import Job, JobStatus
from simcore_service_api_server.models.schemas.solvers import Solver
from simcore_service_api_server.services.director_v2 import ComputationTaskGet
from simcore_service_api_server.utils.http_calls_capture import HttpApiCallCaptureModel
from unit.conftest import SideEffectCallback


def _start_job_side_effect(
    request: httpx.Request,
    path_params: dict[str, Any],
    capture: HttpApiCallCaptureModel,
) -> Any:
    return capture.response_body


def get_inspect_job_side_effect(job_id: str) -> SideEffectCallback:
    def _inspect_job_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        response = capture.response_body
        assert isinstance(response, dict)
        assert response.get("id") is not None
        response["id"] = job_id
        return response

    return _inspect_job_side_effect


@pytest.mark.parametrize(
    "capture", ["get_job_wallet_found.json", "get_job_wallet_not_found.json"]
)
async def test_get_solver_job_wallet(
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
            response["data"]["walletId"] = _wallet_id
        return response

    respx_mock_from_capture(
        [mocked_webserver_service_api_base],
        project_tests_dir / "mocks" / capture,
        [_get_job_wallet_side_effect, _get_wallet_side_effect],
    )

    solver_key: str = "simcore/services/comp/my_super_hpc_solver"
    solver_version: str = "3.14.0"
    job_id: UUID = UUID("87643648-3a38-44e2-9cfe-d86ab3d50629")
    response = await client.get(
        f"{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs/{job_id}/wallet",
        auth=auth,
    )
    if capture == "get_job_wallet_found.json":
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert isinstance(body, dict)
        assert _wallet_id == body.get("walletId")
    elif capture == "get_job_wallet_not_found.json":
        assert response.status_code == status.HTTP_404_NOT_FOUND
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
        [list[respx.MockRouter], Path, list[SideEffectCallback] | None],
        list[respx.MockRouter],
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

    respx_mock_from_capture(
        [mocked_webserver_service_api_base],
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
        assert response.status_code == status.HTTP_200_OK
        _ = parse_obj_as(PricingUnitGet, response.json())
    elif capture_file == "get_job_pricing_unit_invalid_job.json":
        assert response.status_code == status.HTTP_404_NOT_FOUND
    elif capture_file == "get_job_pricing_unit_invalid_solver.json":
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        pytest.fail()


@pytest.mark.parametrize(
    "capture_name,expected_status_code",
    [("start_job_with_payment.json", 200), ("start_job_not_enough_credit.json", 402)],
)
async def test_start_solver_job_pricing_unit_with_payment(
    client: AsyncClient,
    mocked_webserver_service_api_base,
    mocked_directorv2_service_api_base,
    mocked_groups_extra_properties,
    respx_mock_from_capture: Callable[
        [list[respx.MockRouter], Path, list[SideEffectCallback] | None],
        list[respx.MockRouter],
    ],
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
    faker: Faker,
    capture_name: str,
    expected_status_code: int,
):
    assert mocked_groups_extra_properties
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

    callbacks = [
        _get_job_side_effect,
        _put_pricing_plan_and_unit_side_effect,
        _start_job_side_effect,
    ]
    if expected_status_code == status.HTTP_200_OK:
        callbacks.append(get_inspect_job_side_effect(job_id=_job_id))

    _put_pricing_plan_and_unit_side_effect.was_called = False
    respx_mock_from_capture(
        [mocked_webserver_service_api_base, mocked_directorv2_service_api_base],
        project_tests_dir / "mocks" / capture_name,
        callbacks,
    )

    response = await client.post(
        f"{API_VTAG}/solvers/{_solver_key}/releases/{_version}/jobs/{_job_id}:start",
        auth=auth,
        headers={
            "x-pricing-plan": f"{_pricing_plan_id}",
            "x-pricing-unit": f"{_pricing_unit_id}",
        },
    )
    assert response.status_code == expected_status_code
    if expected_status_code == status.HTTP_200_OK:
        assert _put_pricing_plan_and_unit_side_effect.was_called
        assert response.json()["job_id"] == _job_id


async def test_get_solver_job_pricing_unit_no_payment(
    client: AsyncClient,
    mocked_webserver_service_api_base,
    mocked_directorv2_service_api_base,
    mocked_groups_extra_properties,
    respx_mock_from_capture: Callable[
        [list[respx.MockRouter], Path, list[SideEffectCallback]],
        list[respx.MockRouter],
    ],
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
):
    assert mocked_groups_extra_properties
    _solver_key: str = "simcore/services/comp/isolve"
    _version: str = "2.1.24"
    _job_id: str = "1eefc09b-5d08-4022-bc18-33dedbbd7d0f"

    respx_mock_from_capture(
        [mocked_directorv2_service_api_base, mocked_webserver_service_api_base],
        project_tests_dir / "mocks" / "start_job_no_payment.json",
        [_start_job_side_effect, get_inspect_job_side_effect(job_id=_job_id)],
    )

    response = await client.post(
        f"{API_VTAG}/solvers/{_solver_key}/releases/{_version}/jobs/{_job_id}:start",
        auth=auth,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["job_id"] == _job_id


async def test_stop_job(
    client: AsyncClient,
    mocked_directorv2_service_api_base,
    mocked_groups_extra_properties,
    respx_mock_from_capture: Callable[
        [list[respx.MockRouter], Path, list[SideEffectCallback]],
        list[respx.MockRouter],
    ],
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
):

    _solver_key: Final[str] = "simcore/services/comp/isolve"
    _version: Final[str] = "2.1.24"
    _job_id: Final[str] = "1eefc09b-5d08-4022-bc18-33dedbbd7d0f"

    def _stop_job_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        task = ComputationTaskGet.parse_obj(capture.response_body)
        task.id = UUID(_job_id)

        return jsonable_encoder(task)

    respx_mock_from_capture(
        [mocked_directorv2_service_api_base],
        project_tests_dir / "mocks" / "stop_job.json",
        [_stop_job_side_effect, get_inspect_job_side_effect(job_id=_job_id)],
    )

    response = await client.post(
        f"{API_VTAG}/solvers/{_solver_key}/releases/{_version}/jobs/{_job_id}:stop",
        auth=auth,
    )

    assert response.status_code == status.HTTP_200_OK
    status_ = JobStatus.parse_obj(response.json())
    assert status_.job_id == UUID(_job_id)


@pytest.mark.parametrize(
    "sufficient_credits,expected_status_code",
    [(True, status.HTTP_200_OK), (False, status.HTTP_402_PAYMENT_REQUIRED)],
)
async def test_get_solver_job_outputs(
    client: AsyncClient,
    mocked_webserver_service_api_base,
    mocked_storage_service_api_base,
    mocked_groups_extra_properties,
    mocked_solver_job_outputs,
    respx_mock_from_capture: Callable[
        [list[respx.MockRouter], Path, list[SideEffectCallback]],
        list[respx.MockRouter],
    ],
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
    sufficient_credits: bool,
    expected_status_code: int,
):
    def _sf(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        return capture.response_body

    def _wallet_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ):
        wallet = parse_obj_as(
            Envelope[WalletGetWithAvailableCredits], capture.response_body
        ).data
        assert wallet is not None
        wallet.available_credits = (
            Decimal(10.0) if sufficient_credits else Decimal(-10.0)
        )
        envelope = Envelope[WalletGetWithAvailableCredits]()
        envelope.data = wallet
        return jsonable_encoder(envelope)

    respx_mock_from_capture(
        [mocked_webserver_service_api_base, mocked_storage_service_api_base],
        project_tests_dir / "mocks" / "get_solver_outputs.json",
        [_sf, _sf, _sf, _wallet_side_effect, _sf],
    )

    _solver_key: Final[str] = "simcore/services/comp/isolve"
    _version: Final[str] = "2.1.24"
    _job_id: Final[str] = "1eefc09b-5d08-4022-bc18-33dedbbd7d0f"
    response = await client.get(
        f"{API_VTAG}/solvers/{_solver_key}/releases/{_version}/jobs/{_job_id}/outputs",
        auth=auth,
    )

    assert response.status_code == expected_status_code
