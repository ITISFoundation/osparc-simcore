import httpx
import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.httpx_calls_capture_models import (
    CreateRespxMockCallback,
)
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server._service_job import JobService
from simcore_service_api_server._service_programs import ProgramService
from simcore_service_api_server.api.dependencies.job_service import get_job_service
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


@pytest.fixture
def mock_job_service(
    mocker: MockerFixture,
    app: FastAPI,
    mocked_webserver_rest_api_base,
    create_respx_mock_from_capture: CreateRespxMockCallback,
):
    def _get_job_service():
        job_service = JobService(_webserver_api=app.state.webserver_api)
        return job_service

    app.dependency_overrides[get_job_service] = _get_job_service
    yield
    app.dependency_overrides.pop(get_job_service)


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


async def test_create_program_job(
    auth: httpx.BasicAuth,
    client: AsyncClient,
    mocked_rpc_catalog_service_api: dict[str, MockType],
    mocker: MockerFixture,
    mock_program_service: None,
    mock_job_service: None,
    user_id: UserID,
):
    # Arrange
    program_key = "simcore/services/dynamic/my_program"
    version = "1.0.0"
    headers = {
        "X-Simcore-Parent-Project-Uuid": str(ProjectID("project-uuid")),
        "X-Simcore-Parent-Node-Id": str(NodeID("node-id")),
    }

    # Act
    response = await client.post(
        f"/{API_VTAG}/programs/{program_key}/releases/{version}/jobs",
        headers=headers,
        auth=auth,
    )

    # Assert
    assert response.status_code == status.HTTP_201_CREATED
    job = Job.model_validate(response.json())
    assert job.id == "job-id"
    assert job.url == "http://testserver/v0/jobs/job-id"
