# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
import respx
import yarl
from aioresponses import aioresponses as AioResponsesMock
from faker import Faker
from fastapi import status
from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
from models_library.api_schemas_storage import (
    ETag,
    FileUploadCompletionBody,
    UploadedPart,
)
from models_library.basic_types import SHA256Str
from pydantic import TypeAdapter
from pytest_simcore.helpers.httpx_calls_capture_models import (
    CreateRespxMockCallback,
    HttpApiCallCaptureModel,
)
from respx import MockRouter
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.pagination import Page
from simcore_service_api_server.models.schemas.files import (
    ClientFile,
    ClientFileUploadData,
    File,
)

_FAKER = Faker()


class DummyFileData:
    """Static class for providing consistent dummy file data for testing"""

    _file_id: UUID = UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
    _file_name: str = "myfile.txt"
    _final_e_tag: ETag = "07d1c1a4-b073-4be7-b022-f405d90e99aa"
    _file_size: int = 100000
    _file_sha256_checksum: SHA256Str = SHA256Str(
        "E7a5B06A880dDee55A16fbc27Dc29705AE1aceadcaf0aDFd15fAF839ff5E2C2e"
    )

    @classmethod
    def file(cls) -> File:
        return File(
            id=File.create_id(
                cls._file_size,
                cls._file_name,
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            ),
            filename=cls._file_name,
            e_tag="",
            sha256_checksum=cls._file_sha256_checksum,
        )

    @classmethod
    def client_file(cls) -> ClientFile:
        return TypeAdapter(ClientFile).validate_python(
            {
                "filename": cls._file_name,
                "filesize": cls._file_size,
                "sha256_checksum": cls._file_sha256_checksum,
            },
        )

    @classmethod
    def file_size(cls) -> int:
        return cls._file_size

    @classmethod
    def uploaded_parts(cls) -> FileUploadCompletionBody:
        return FileUploadCompletionBody(
            parts=[UploadedPart(number=ii + 1, e_tag=_FAKER.uuid4()) for ii in range(5)]
        )

    @classmethod
    def final_e_tag(cls) -> ETag:
        return cls._final_e_tag

    @classmethod
    def checksum(cls) -> SHA256Str:
        return cls._file_sha256_checksum


@pytest.mark.xfail(reason="Under dev")
async def test_list_files_legacy(
    client: AsyncClient, mocked_storage_service_api_base: MockRouter
):
    response = await client.get(f"{API_VTAG}/files")

    assert response.status_code == status.HTTP_200_OK

    TypeAdapter(File).validate_python(response.json())

    assert response.json() == [
        {
            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "filename": "string",
            "content_type": "string",
            "checksum": "string",
        }
    ]


@pytest.mark.xfail(reason="Under dev")
async def test_list_files_with_pagination(
    client: AsyncClient,
    mocked_storage_service_api_base: MockRouter,
):
    response = await client.get(f"{API_VTAG}/files/page")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "items": [
            {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "filename": "string",
                "content_type": "string",
                "checksum": "string",
            }
        ],
        "total": 0,
        "limit": 1,
        "offset": 0,
        "links": {
            "first": "/api/v1/users?limit=1&offset1",
            "last": "/api/v1/users?limit=1&offset1",
            "self": "/api/v1/users?limit=1&offset1",
            "next": "/api/v1/users?limit=1&offset1",
            "prev": "/api/v1/users?limit=1&offset1",
        },
    }


@pytest.mark.xfail(reason="Under dev")
async def test_upload_content(
    client: AsyncClient, mocked_storage_service_api_base: MockRouter, tmp_path: Path
):
    upload_path = tmp_path / "test_upload_content.txt"
    upload_path.write_text("test_upload_content")

    response = await client.put(
        f"{API_VTAG}/files/content", files={"upload-file": upload_path.open("rb")}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "filename": upload_path.name,
        "content_type": "string",
        "checksum": "string",
    }


@pytest.mark.xfail(reason="Under dev")
async def test_get_file(
    client: AsyncClient, mocked_storage_service_api_base: MockRouter, tmp_path: Path
):
    response = await client.get(
        f"{API_VTAG}/files/3fa85f64-5717-4562-b3fc-2c963f66afa6"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "filename": "string",
        "content_type": "string",
        "checksum": "string",
    }


async def test_delete_file(
    client: AsyncClient,
    mocked_storage_service_api_base: respx.MockRouter,
    create_respx_mock_from_capture: CreateRespxMockCallback,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
):
    def search_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> dict[str, Any]:
        assert isinstance(capture.response_body, dict)
        response: dict[str, Any] = capture.response_body
        return response

    def delete_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        return capture.response_body

    create_respx_mock_from_capture(
        respx_mocks=[mocked_storage_service_api_base],
        capture_path=project_tests_dir / "mocks" / "delete_file.json",
        side_effects_callbacks=[search_side_effect, delete_side_effect],
    )

    response = await client.delete(
        f"{API_VTAG}/files/3fa85f64-5717-4562-b3fc-2c963f66afa6", auth=auth
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.xfail(reason="Under dev")
async def test_download_content(
    client: AsyncClient, mocked_storage_service_api_base: MockRouter, tmp_path: Path
):
    response = await client.get(
        f"{API_VTAG}/files/3fa85f64-5717-4562-b3fc-2c963f66afa6/content"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/octet-stream"


@pytest.mark.parametrize("follow_up_request", ["complete", "abort"])
async def test_get_upload_links(
    follow_up_request: str,
    client: AsyncClient,
    auth: httpx.BasicAuth,
    storage_v0_service_mock: AioResponsesMock,
):
    """Test that we can get data needed for performing multipart upload directly to S3"""

    assert storage_v0_service_mock  # nosec

    msg = {
        "filename": DummyFileData.file().filename,
        "filesize": DummyFileData.file_size(),
        "sha256_checksum": DummyFileData.checksum(),
    }

    response = await client.post(f"{API_VTAG}/files/content", json=msg, auth=auth)

    payload: dict[str, str] = response.json()

    assert response.status_code == status.HTTP_200_OK
    client_upload_schema: ClientFileUploadData = ClientFileUploadData.model_validate(
        payload
    )

    if follow_up_request == "complete":
        body = {
            "client_file": jsonable_encoder(DummyFileData.client_file()),
            "uploaded_parts": jsonable_encoder(DummyFileData.uploaded_parts()),
        }
        response = await client.post(
            client_upload_schema.upload_schema.links.complete_upload,
            json=body,
            auth=auth,
        )

        payload: dict[str, str] = response.json()

        assert response.status_code == status.HTTP_200_OK
        file: File = File.model_validate(payload)
        assert file.sha256_checksum == DummyFileData.checksum()
    elif follow_up_request == "abort":
        body = {
            "client_file": jsonable_encoder(DummyFileData.client_file()),
        }
        response = await client.post(
            client_upload_schema.upload_schema.links.abort_upload, json=body, auth=auth
        )
        assert response.status_code == status.HTTP_200_OK
    else:
        raise AssertionError


@pytest.mark.parametrize(
    "query",
    [
        {"sha256_checksum": str(DummyFileData.checksum())},
        {"file_id": str(DummyFileData.file().id)},
        {
            "file_id": str(DummyFileData.file().id),
            "sha256_checksum": str(DummyFileData.checksum()),
        },
    ],
    ids=lambda x: "&".join([f"{k}={v}" for k, v in x.items()]),
)
async def test_search_file(
    query: dict[str, str],
    client: AsyncClient,
    mocked_storage_service_api_base: respx.MockRouter,
    create_respx_mock_from_capture: CreateRespxMockCallback,
    auth: httpx.BasicAuth,
    project_tests_dir: Path,
):
    def side_effect_callback(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> dict[str, Any]:
        url: yarl.URL = yarl.URL(f"{request.url}")
        request_query: dict[str, str] = dict(url.query)
        assert isinstance(capture.response_body, dict)
        response: dict[str, Any] = capture.response_body
        for key in query:
            if key == "sha256_checksum":
                response["data"][0][key] = request_query[key]
            elif key == "file_id":
                file_uuid_parts: list[str] = response["data"][0]["file_uuid"].split("/")
                file_uuid_parts[1] = request_query["startswith"].split("/")[1]
                response["data"][0]["file_uuid"] = "/".join(file_uuid_parts)
                response["data"][0]["file_id"] = "/".join(file_uuid_parts)
            else:
                msg = f"Encountered unexpected {key=}"
                raise ValueError(msg)
        return response

    create_respx_mock_from_capture(
        respx_mocks=[mocked_storage_service_api_base],
        capture_path=project_tests_dir / "mocks" / "search_file_checksum.json",
        side_effects_callbacks=[side_effect_callback],
    )

    response = await client.get(f"{API_VTAG}/files:search", auth=auth, params=query)
    assert response.status_code == status.HTTP_200_OK
    page: Page[File] = TypeAdapter(Page[File]).validate_python(response.json())
    assert len(page.items) == page.total
    file = page.items[0]
    if "sha256_checksum" in query:
        assert file.sha256_checksum == SHA256Str(query["sha256_checksum"])
    if "file_id" in query:
        assert file.id == UUID(query["file_id"])


async def test_download_file_openapi_specs(openapi_dev_specs: dict[str, Any]):
    """Test that openapi-specs for download file entrypoint specifies a binary file is returned in case of return status 200"""
    file_download_responses: dict[str, Any] = openapi_dev_specs["paths"][
        f"/{API_VTAG}/files/{{file_id}}/content"
    ]["get"]["responses"]
    assert "application/octet-stream" in file_download_responses["200"]["content"]
