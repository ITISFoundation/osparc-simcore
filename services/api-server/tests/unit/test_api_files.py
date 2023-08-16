import datetime

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from aioresponses import aioresponses as AioResponsesMock
from faker import Faker
from fastapi import status
from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
from models_library.api_schemas_storage import (
    ETag,
    FileUploadCompletionBody,
    FileUploadSchema,
    UploadedPart,
)
from pydantic import parse_obj_as
from respx import MockRouter
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.files import ClientFile, File

_FAKER = Faker()


class DummyFileData:
    """Static class for providing consistent dummy file data for testing"""

    _file_id: UUID = UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
    _file_name: str = "myfile.txt"
    _final_e_tag: ETag = "07d1c1a4-b073-4be7-b022-f405d90e99aa"
    _file_size: int = 100000

    @classmethod
    def file(cls) -> File:
        return File(
            id=File.create_id(
                cls._file_size,
                cls._file_name,
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            ),
            filename=cls._file_name,
            checksum="",
        )

    @classmethod
    def client_file(cls) -> ClientFile:
        return parse_obj_as(
            ClientFile, {"filename": cls._file_name, "filesize": cls._file_size}
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


@pytest.mark.xfail(reason="Under dev")
async def test_list_files_legacy(
    client: AsyncClient, mocked_storage_service_api_base: MockRouter
):
    response = await client.get(f"{API_VTAG}/files")

    assert response.status_code == status.HTTP_200_OK

    parse_obj_as(File, response.json())

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


@pytest.mark.xfail(reason="Under dev")
async def test_delete_file(
    client: AsyncClient, mocked_storage_service_api_base: MockRouter, tmp_path: Path
):
    response = await client.delete(
        f"{API_VTAG}/files/3fa85f64-5717-4562-b3fc-2c963f66afa6"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT


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
    }

    response = await client.post(f"{API_VTAG}/files/content", json=msg, auth=auth)

    payload: dict[str, str] = response.json()

    assert response.status_code == status.HTTP_200_OK
    upload_schema: FileUploadSchema = FileUploadSchema.parse_obj(payload)

    if follow_up_request == "complete":
        body = {
            "client_file": jsonable_encoder(DummyFileData.client_file()),
            "uploaded_parts": jsonable_encoder(DummyFileData.uploaded_parts()),
        }
        response = await client.post(
            upload_schema.links.complete_upload,
            json=body,
            auth=auth,
        )

        payload: dict[str, str] = response.json()

        assert response.status_code == status.HTTP_200_OK
        _ = parse_obj_as(File, payload)
    elif follow_up_request == "abort":
        body = {
            "client_file": jsonable_encoder(DummyFileData.client_file()),
        }
        response = await client.post(
            upload_schema.links.abort_upload, json=body, auth=auth
        )
        assert response.status_code == status.HTTP_200_OK
    else:
        assert False
