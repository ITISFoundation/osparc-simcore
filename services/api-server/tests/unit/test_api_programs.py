import json
from functools import partial
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from models_library.api_schemas_storage.storage_schemas import FileUploadSchema
from models_library.users import UserID
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.httpx_calls_capture_models import (
    CreateRespxMockCallback,
    HttpApiCallCaptureModel,
)
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server._service_programs import ProgramService
from simcore_service_api_server.api.dependencies.program_service import (
    get_program_service,
)
from simcore_service_api_server.models.schemas.jobs import Job
from simcore_service_api_server.models.schemas.programs import Program
from simcore_service_api_server.services_rpc.catalog import CatalogService


@pytest.fixture
def mock_program_service(mocker: MockerFixture, app: FastAPI):

    def _get_program_service():
        catalog_service = CatalogService(_client=mocker.MagicMock())
        return ProgramService(_catalog_service=catalog_service)

    app.dependency_overrides[get_program_service] = _get_program_service
    yield
    app.dependency_overrides.pop(get_program_service)


async def test_get_program_release(
    auth: httpx.BasicAuth,
    client: AsyncClient,
    mocked_rpc_catalog_service_api: dict[str, MockType],
    mocker: MockerFixture,
    mock_program_service: None,
    user_id: UserID,
):
    # Arrange
    program_key = "simcore/services/dynamic/my_program"
    version = "1.0.0"

    response = await client.get(
        f"/{API_VTAG}/programs/{program_key}/releases/{version}", auth=auth
    )

    # Assert
    assert response.status_code == status.HTTP_200_OK
    program = Program.model_validate(response.json())
    assert program.id == program_key
    assert program.version == version


@pytest.mark.parametrize("capture_name", ["create_program_job_success.json"])
async def test_create_program_job(
    auth: httpx.BasicAuth,
    client: AsyncClient,
    mocked_webserver_rest_api_base,
    mocked_rpc_catalog_service_api: dict[str, MockType],
    create_respx_mock_from_capture: CreateRespxMockCallback,
    mocker: MockerFixture,
    mock_program_service: None,
    user_id: UserID,
    capture_name: str,
    project_tests_dir: Path,
):

    mocker.patch(
        "simcore_service_api_server.api.routes.programs.get_upload_links_from_s3",
        return_value=(
            None,
            FileUploadSchema.model_validate(
                next(iter(FileUploadSchema.model_json_schema()["examples"]))
            ),
        ),
    )
    mocker.patch("simcore_service_api_server.api.routes.programs.complete_file_upload")

    def _side_effect(
        server_state: dict,
        request: httpx.Request,
        kwargs: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> dict[str, Any]:

        response_body = capture.response_body

        # first call defines the project uuid
        if server_state.get("project_uuid") is None:
            _project_uuid = json.loads(request.content.decode("utf-8")).get("uuid")
            assert _project_uuid
            server_state["project_uuid"] = _project_uuid

        if request.url.path.endswith("/result"):
            capture_uuid = response_body["data"]["uuid"]
            response_body["data"]["uuid"] = server_state["project_uuid"]
            response_body["data"]["name"] = response_body["data"]["name"].replace(
                capture_uuid, server_state["project_uuid"]
            )
        assert isinstance(response_body, dict)
        return response_body

    # simulate server state
    _server_state = dict()

    create_respx_mock_from_capture(
        respx_mocks=[mocked_webserver_rest_api_base],
        capture_path=project_tests_dir / "mocks" / capture_name,
        side_effects_callbacks=3 * [partial(_side_effect, _server_state)],
    )

    # Arrange
    program_key = "simcore/services/dynamic/electrode-selector"
    version = "2.1.3"

    response = await client.post(
        f"/{API_VTAG}/programs/{program_key}/releases/{version}/jobs",
        # headers=headers,
        auth=auth,
    )

    # Assert
    assert response.status_code == status.HTTP_201_CREATED
    job = Job.model_validate(response.json())
