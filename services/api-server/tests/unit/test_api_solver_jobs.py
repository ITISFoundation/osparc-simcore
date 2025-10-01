# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final
from uuid import UUID, uuid4

import httpx
import pytest
from faker import Faker
from fastapi import status
from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
from models_library.generics import Envelope
from models_library.projects_nodes import Node
from models_library.rpc.webserver.projects import ProjectJobRpcGet
from pydantic import TypeAdapter
from pytest_mock import MockType
from pytest_simcore.helpers.httpx_calls_capture_models import (
    CreateRespxMockCallback,
    HttpApiCallCaptureModel,
    SideEffectCallback,
)
from respx import MockRouter
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.jobs import Job, JobStatus
from simcore_service_api_server.models.schemas.model_adapter import (
    PricingUnitGetLegacy,
    WalletGetWithAvailableCreditsLegacy,
)
from simcore_service_api_server.models.schemas.solvers import Solver
from simcore_service_api_server.services_http.director_v2 import ComputationTaskGet


def _start_job_side_effect(
    request: httpx.Request,
    path_params: dict[str, Any],
    capture: HttpApiCallCaptureModel,
) -> Any:
    return capture.response_body


def _get_inspect_job_side_effect(job_id: str) -> SideEffectCallback:
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
    mocked_webserver_rest_api_base: MockRouter,
    create_respx_mock_from_capture: CreateRespxMockCallback,
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

    create_respx_mock_from_capture(
        respx_mocks=[mocked_webserver_rest_api_base],
        capture_path=project_tests_dir / "mocks" / capture,
        side_effects_callbacks=[_get_job_wallet_side_effect, _get_wallet_side_effect],
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
        pytest.fail(reason=f"Uknown {capture=}")


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
    mocked_webserver_rest_api_base: MockRouter,
    create_respx_mock_from_capture: CreateRespxMockCallback,
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

    create_respx_mock_from_capture(
        respx_mocks=[mocked_webserver_rest_api_base],
        capture_path=project_tests_dir / "mocks" / capture_file,
        side_effects_callbacks=(
            [_get_job_side_effect, _get_pricing_unit_side_effect]
            if capture_file == "get_job_pricing_unit_success.json"
            else [_get_job_side_effect]
        ),
    )

    response = await client.get(
        f"{API_VTAG}/solvers/{solver_key}/releases/{solver_version}/jobs/{job_id}/pricing_unit",
        auth=auth,
    )
    if capture_file == "get_job_pricing_unit_success.json":
        assert response.status_code == status.HTTP_200_OK
        _ = TypeAdapter(PricingUnitGetLegacy).validate_python(response.json())
    elif capture_file == "get_job_pricing_unit_invalid_job.json":
        assert response.status_code == status.HTTP_404_NOT_FOUND
    elif capture_file == "get_job_pricing_unit_invalid_solver.json":
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        pytest.fail(reason=f"Unknown {capture_file=}")


@pytest.mark.parametrize(
    "capture_name,expected_status_code",
    [
        ("start_job_with_payment.json", 202),
        ("start_job_not_enough_credit.json", 402),
    ],
)
async def test_start_solver_job_pricing_unit_with_payment(
    mocked_app_dependencies: None,
    client: AsyncClient,
    mocked_webserver_rest_api_base: MockRouter,
    mocked_directorv2_rest_api_base: MockRouter,
    mocked_webserver_rpc_api: dict[str, MockType],
    create_respx_mock_from_capture: CreateRespxMockCallback,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
    faker: Faker,
    capture_name: str,
    expected_status_code: int,
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

    callbacks = [
        _get_job_side_effect,
        _put_pricing_plan_and_unit_side_effect,
        _start_job_side_effect,
    ]
    if expected_status_code == status.HTTP_202_ACCEPTED:
        callbacks.append(_get_inspect_job_side_effect(job_id=_job_id))

    _put_pricing_plan_and_unit_side_effect.was_called = False
    create_respx_mock_from_capture(
        respx_mocks=[
            mocked_webserver_rest_api_base,
            mocked_directorv2_rest_api_base,
        ],
        capture_path=project_tests_dir / "mocks" / capture_name,
        side_effects_callbacks=callbacks,
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
    if expected_status_code == status.HTTP_202_ACCEPTED:
        assert _put_pricing_plan_and_unit_side_effect.was_called
        assert response.json()["job_id"] == _job_id


async def test_get_solver_job_pricing_unit_no_payment(
    mocked_app_dependencies: None,
    client: AsyncClient,
    mocked_webserver_rest_api_base: MockRouter,
    mocked_directorv2_rest_api_base: MockRouter,
    mocked_webserver_rpc_api: dict[str, MockType],
    create_respx_mock_from_capture: CreateRespxMockCallback,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
):
    _solver_key: str = "simcore/services/comp/isolve"
    _version: str = "2.1.24"
    _job_id: str = "1eefc09b-5d08-4022-bc18-33dedbbd7d0f"

    create_respx_mock_from_capture(
        respx_mocks=[
            mocked_directorv2_rest_api_base,
            mocked_webserver_rest_api_base,
        ],
        capture_path=project_tests_dir / "mocks" / "start_job_no_payment.json",
        side_effects_callbacks=[
            _start_job_side_effect,
            _get_inspect_job_side_effect(job_id=_job_id),
        ],
    )

    response = await client.post(
        f"{API_VTAG}/solvers/{_solver_key}/releases/{_version}/jobs/{_job_id}:start",
        auth=auth,
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["job_id"] == _job_id


async def test_start_solver_job_conflict(
    mocked_app_dependencies: None,
    client: AsyncClient,
    mocked_webserver_rest_api_base: MockRouter,
    mocked_directorv2_rest_api_base: MockRouter,
    mocked_webserver_rpc_api: dict[str, MockType],
    create_respx_mock_from_capture: CreateRespxMockCallback,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
):
    _solver_key: str = "simcore/services/comp/itis/sleeper"
    _version: str = "2.0.2"
    _job_id: str = "b9faf8d8-4928-4e50-af40-3690712c5481"

    create_respx_mock_from_capture(
        respx_mocks=[
            mocked_directorv2_rest_api_base,
            mocked_webserver_rest_api_base,
        ],
        capture_path=project_tests_dir / "mocks" / "start_solver_job.json",
        side_effects_callbacks=[
            _start_job_side_effect,
            _get_inspect_job_side_effect(job_id=_job_id),
        ],
    )

    response = await client.post(
        f"{API_VTAG}/solvers/{_solver_key}/releases/{_version}/jobs/{_job_id}:start",
        auth=auth,
    )

    assert response.status_code == status.HTTP_200_OK
    job_status = JobStatus.model_validate(response.json())
    assert f"{job_status.job_id}" == _job_id


@pytest.mark.parametrize(
    "fake_project_job_rpc_get",
    [
        pytest.param(
            ProjectJobRpcGet(
                uuid=UUID("00000000-1234-5678-1234-123456789012"),
                name="A study job",
                description="A description of a study job with many node",
                workbench={},
                created_at=datetime.fromisoformat("2023-02-01T00:00:00Z"),
                modified_at=datetime.fromisoformat("2023-02-01T00:00:00Z"),
                job_parent_resource_name="studies/96642f2a-a72c-11ef-8776-02420a00087d",
                storage_assets_deleted=True,
            ),
            id="storage_assets_deleted",
        )
    ],
)
async def test_start_solver_job_storage_data_missing(
    client: AsyncClient,
    mocked_webserver_rest_api_base: MockRouter,
    mocked_directorv2_rest_api_base: MockRouter,
    mocked_webserver_rpc_api: dict[str, MockType],
    create_respx_mock_from_capture: CreateRespxMockCallback,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
):
    _solver_key: str = "simcore/services/comp/itis/sleeper"
    _version: str = "2.0.2"
    _job_id: str = "b9faf8d8-4928-4e50-af40-3690712c5481"

    create_respx_mock_from_capture(
        respx_mocks=[
            mocked_directorv2_rest_api_base,
            mocked_webserver_rest_api_base,
        ],
        capture_path=project_tests_dir / "mocks" / "start_solver_job.json",
        side_effects_callbacks=[
            _start_job_side_effect,
            _get_inspect_job_side_effect(job_id=_job_id),
        ],
    )

    response = await client.post(
        f"{API_VTAG}/solvers/{_solver_key}/releases/{_version}/jobs/{_job_id}:start",
        auth=auth,
    )

    assert response.status_code == status.HTTP_409_CONFLICT


async def test_stop_job(
    client: AsyncClient,
    mocked_directorv2_rest_api_base: MockRouter,
    create_respx_mock_from_capture: CreateRespxMockCallback,
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
        task = ComputationTaskGet.model_validate(capture.response_body)
        task.id = UUID(_job_id)

        return jsonable_encoder(task)

    create_respx_mock_from_capture(
        respx_mocks=[mocked_directorv2_rest_api_base],
        capture_path=project_tests_dir / "mocks" / "stop_job.json",
        side_effects_callbacks=[
            _stop_job_side_effect,
            _get_inspect_job_side_effect(job_id=_job_id),
        ],
    )

    response = await client.post(
        f"{API_VTAG}/solvers/{_solver_key}/releases/{_version}/jobs/{_job_id}:stop",
        auth=auth,
    )

    assert response.status_code == status.HTTP_200_OK
    status_ = JobStatus.model_validate(response.json())
    assert status_.job_id == UUID(_job_id)


@pytest.mark.parametrize(
    "sufficient_credits,expected_status_code",
    [(True, status.HTTP_200_OK), (False, status.HTTP_402_PAYMENT_REQUIRED)],
)
async def test_get_solver_job_outputs(
    client: AsyncClient,
    mocked_webserver_rest_api_base: MockRouter,
    mocked_storage_rest_api_base: MockRouter,
    mocked_solver_job_outputs: None,
    mocked_webserver_rpc_api: dict[str, MockType],
    create_respx_mock_from_capture: CreateRespxMockCallback,
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
        wallet = (
            TypeAdapter(Envelope[WalletGetWithAvailableCreditsLegacy])
            .validate_python(capture.response_body)
            .data
        )
        assert wallet is not None
        wallet.available_credits = (
            Decimal(10.0) if sufficient_credits else Decimal(-10.0)
        )
        envelope = Envelope[WalletGetWithAvailableCreditsLegacy]()
        envelope.data = wallet
        return jsonable_encoder(envelope)

    create_respx_mock_from_capture(
        respx_mocks=[
            mocked_webserver_rest_api_base,
            mocked_storage_rest_api_base,
        ],
        capture_path=project_tests_dir / "mocks" / "get_solver_outputs.json",
        side_effects_callbacks=[_sf, _sf, _sf, _wallet_side_effect, _sf],
    )

    _solver_key: Final[str] = "simcore/services/comp/isolve"
    _version: Final[str] = "2.1.24"
    _job_id: Final[str] = "1eefc09b-5d08-4022-bc18-33dedbbd7d0f"
    response = await client.get(
        f"{API_VTAG}/solvers/{_solver_key}/releases/{_version}/jobs/{_job_id}/outputs",
        auth=auth,
    )

    assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    "fake_project_job_rpc_get",
    [
        ProjectJobRpcGet(
            uuid=UUID("12345678-1234-5678-1234-123456789012"),
            name="A solver job",
            description="A description of a solver job with a single node",
            workbench={
                f"{uuid4()}": Node.model_validate(
                    Node.model_json_schema()["examples"][0]
                )
            },
            created_at=datetime.fromisoformat("2023-01-01T00:00:00Z"),
            modified_at=datetime.fromisoformat("2023-01-01T00:00:00Z"),
            job_parent_resource_name="solvers/simcore%2Fservices%2Fcomp%2Fitis%2Fsleeper/releases/2.0.2",
            storage_assets_deleted=True,
        )
    ],
)
async def test_get_solver_job_outputs_assets_deleted(
    client: AsyncClient,
    mocked_webserver_rest_api_base: MockRouter,
    mocked_storage_rest_api_base: MockRouter,
    mocked_solver_job_outputs: None,
    mocked_webserver_rpc_api: dict[str, MockType],
    create_respx_mock_from_capture: CreateRespxMockCallback,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
):
    def _sf(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        return capture.response_body

    create_respx_mock_from_capture(
        respx_mocks=[
            mocked_webserver_rest_api_base,
            mocked_storage_rest_api_base,
        ],
        capture_path=project_tests_dir / "mocks" / "get_solver_outputs.json",
        side_effects_callbacks=[_sf, _sf, _sf, _sf, _sf],
    )

    _solver_key: Final[str] = "simcore/services/comp/isolve"
    _version: Final[str] = "2.1.24"
    _job_id: Final[str] = "1eefc09b-5d08-4022-bc18-33dedbbd7d0f"
    response = await client.get(
        f"{API_VTAG}/solvers/{_solver_key}/releases/{_version}/jobs/{_job_id}/outputs",
        auth=auth,
    )

    assert response.status_code == status.HTTP_409_CONFLICT
