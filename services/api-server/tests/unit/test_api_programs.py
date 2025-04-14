from pathlib import Path

import httpx
import pytest
from fastapi import status
from httpx import AsyncClient
from pytest_simcore.helpers.httpx_calls_capture_models import CreateRespxMockCallback
from simcore_service_api_server._meta import API_VTAG


@pytest.mark.parametrize(
    "capture,expected_status_code",
    [
        ("create_program_job_invalid_program.json", status.HTTP_404_NOT_FOUND),
        ("create_program_job_success.json", status.HTTP_201_CREATED),
    ],
)
async def test_create_program_job(
    client: AsyncClient,
    mocked_webserver_rest_api_base,
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

    program_key = "simcore/services/comp/my_program"
    version = "1.0.0"

    response = await client.post(
        f"{API_VTAG}/programs/{program_key}/releases/{version}/jobs",
        auth=auth,
    )
    assert response.status_code == expected_status_code
    if response.status_code == status.HTTP_201_CREATED:
        assert "job_id" in response.json()


@pytest.mark.parametrize(
    "capture,expected_status_code",
    [
        ("list_programs_success.json", status.HTTP_200_OK),
    ],
)
async def test_list_programs(
    client: AsyncClient,
    mocked_catalog_rest_api_base,
    create_respx_mock_from_capture: CreateRespxMockCallback,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
    capture: str,
    expected_status_code: int,
):
    respx_mock = create_respx_mock_from_capture(
        respx_mocks=[mocked_catalog_rest_api_base],
        capture_path=project_tests_dir / "mocks" / capture,
        side_effects_callbacks=[],
    )
    assert respx_mock

    response = await client.get(f"{API_VTAG}/programs", auth=auth)
    assert response.status_code == expected_status_code
    if response.status_code == status.HTTP_200_OK:
        programs = response.json()
        assert isinstance(programs, list)


@pytest.mark.parametrize(
    "capture,expected_status_code",
    [
        ("get_program_release_success.json", status.HTTP_200_OK),
        ("get_program_release_not_found.json", status.HTTP_404_NOT_FOUND),
    ],
)
async def test_get_program_release(
    client: AsyncClient,
    mocked_catalog_rest_api_base,
    create_respx_mock_from_capture: CreateRespxMockCallback,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
    capture: str,
    expected_status_code: int,
):
    respx_mock = create_respx_mock_from_capture(
        respx_mocks=[mocked_catalog_rest_api_base],
        capture_path=project_tests_dir / "mocks" / capture,
        side_effects_callbacks=[],
    )
    assert respx_mock

    program_key = "simcore/services/dynamic/electrode-selector"
    version = "2.1.3"

    response = await client.get(
        f"{API_VTAG}/programs/{program_key}/releases/{version}", auth=auth
    )
    assert response.status_code == expected_status_code
    if response.status_code == status.HTTP_200_OK:
        program_release = response.json()
        assert "id" in program_release
        assert program_release["id"] == program_key
        assert program_release["version"] == version
