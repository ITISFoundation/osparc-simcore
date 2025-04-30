# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

import httpx
import pytest
from common_library.json_serialization import json_loads
from fastapi import status
from httpx import AsyncClient
from models_library.api_schemas_storage.storage_schemas import FileUploadSchema
from models_library.rpc_pagination import PageRpc
from models_library.services_history import ServiceRelease
from models_library.users import UserID
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.faker_factories import DEFAULT_FAKER
from pytest_simcore.helpers.httpx_calls_capture_models import (
    CreateRespxMockCallback,
    HttpApiCallCaptureModel,
)
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.jobs import Job
from simcore_service_api_server.models.schemas.programs import Program


async def test_get_program_release(
    auth: httpx.BasicAuth,
    client: AsyncClient,
    mocked_catalog_rpc_api: dict[str, MockType],
    mocker: MockerFixture,
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
    assert program.version_display is not None


@pytest.mark.parametrize(
    "job_name,job_description",
    [
        (None, None),
        (DEFAULT_FAKER.name(), None),
        (None, DEFAULT_FAKER.sentence()),
        (DEFAULT_FAKER.name(), DEFAULT_FAKER.sentence()),
    ],
)
@pytest.mark.parametrize("capture_name", ["create_program_job_success.json"])
async def test_create_program_job(
    auth: httpx.BasicAuth,
    client: AsyncClient,
    mocked_webserver_rest_api_base,
    mocked_webserver_rpc_api: dict[str, MockType],
    mocked_catalog_rpc_api: dict[str, MockType],
    create_respx_mock_from_capture: CreateRespxMockCallback,
    mocker: MockerFixture,
    user_id: UserID,
    capture_name: str,
    project_tests_dir: Path,
    job_name: str | None,
    job_description: str | None,
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

        # first call creates project
        if server_state.get("project_uuid") is None:
            get_body_field = lambda field: json_loads(
                request.content.decode("utf-8")
            ).get(field)

            _project_uuid = get_body_field("uuid")
            assert _project_uuid
            server_state["project_uuid"] = _project_uuid

            _name = get_body_field("name")
            assert _name
            server_state["name"] = _name

            _description = get_body_field("description")
            assert _description
            server_state["description"] = _description

            if job_name:
                assert job_name == get_body_field("name")
            if job_description:
                assert job_description == get_body_field("description")

        if request.url.path.endswith("/result"):
            response_body["data"]["uuid"] = server_state["project_uuid"]
            response_body["data"]["name"] = server_state["name"]
            response_body["data"]["description"] = server_state["description"]
        assert isinstance(response_body, dict)
        return response_body

    # simulate server state
    _server_state = dict()

    create_respx_mock_from_capture(
        respx_mocks=[mocked_webserver_rest_api_base],
        capture_path=project_tests_dir / "mocks" / capture_name,
        side_effects_callbacks=3 * [partial(_side_effect, _server_state)],
    )

    program_key = "simcore/services/dynamic/electrode-selector"
    version = "2.1.3"

    body = {"name": job_name, "description": job_description}

    response = await client.post(
        f"/{API_VTAG}/programs/{program_key}/releases/{version}/jobs",
        auth=auth,
        json={k: v for k, v in body.items() if v is not None},
    )

    # Assert
    assert response.status_code == status.HTTP_201_CREATED
    job = Job.model_validate(response.json())


async def test_list_latest_programs(
    auth: httpx.BasicAuth,
    client: AsyncClient,
    mocked_catalog_rpc_api: dict[str, MockType],
):
    # Arrange
    response = await client.get(f"/{API_VTAG}/programs", auth=auth)
    assert response.status_code == status.HTTP_200_OK


async def test_list_program_history(
    auth: httpx.BasicAuth,
    client: AsyncClient,
    mocked_catalog_rpc_api: dict[str, MockType],
):
    program_key = "simcore/services/dynamic/my_program"
    # Arrange
    response = await client.get(
        f"/{API_VTAG}/programs/{program_key}/releases", auth=auth
    )
    assert response.status_code == status.HTTP_200_OK


@dataclass
class _MockCatalogRpcSideEffects:
    async def list_services_paginated(*args, **kwargs): ...
    async def get_service(*args, **kwargs): ...
    async def update_service(*args, **kwargs): ...
    async def get_service_ports(*args, **kwargs): ...
    async def list_my_service_history_latest_first(*args, **kwargs):
        return PageRpc[ServiceRelease].create(
            [],
            total=0,
            limit=10,
            offset=0,
        )


@pytest.mark.parametrize(
    "catalog_rpc_side_effects", [_MockCatalogRpcSideEffects()], indirect=True
)
async def test_list_program_history_no_program(
    auth: httpx.BasicAuth,
    client: AsyncClient,
    mocked_catalog_rpc_api: dict[str, MockType],
):
    program_key = "simcore/services/dynamic/my_program"
    # Arrange
    response = await client.get(
        f"/{API_VTAG}/programs/{program_key}/releases", auth=auth
    )
    assert response.status_code == status.HTTP_200_OK
