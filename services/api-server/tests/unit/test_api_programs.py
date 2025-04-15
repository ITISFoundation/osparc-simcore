import httpx
import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from models_library.users import UserID
from pytest_mock import MockerFixture, MockType
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server._service_programs import ProgramService
from simcore_service_api_server.api.dependencies.program_service import (
    get_program_service,
)
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


@pytest.mark.asyncio
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
