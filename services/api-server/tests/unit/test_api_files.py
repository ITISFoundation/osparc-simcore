# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
from pathlib import Path

import httpx
import pytest
from aioresponses import aioresponses as AioResponsesMock
from fastapi import status
from httpx import AsyncClient
from pydantic import parse_obj_as
from pytest_simcore.services_api_mocks_for_aiohttp_clients import (
    DummyFileData,
    storage_v0_service_mock,
)
from respx import MockRouter
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.files import ClientFileUploadSchema, File

pytest_plugins = [
    "pytest_simcore.aioresponses_mocker",
]


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


@pytest.mark.testit
@pytest.mark.parametrize("follow_up_request", ["complete", "abort"])
async def test_get_upload_links(
    follow_up_request: str,
    client: AsyncClient,
    auth: httpx.BasicAuth,
    storage_v0_service_mock: AioResponsesMock,
):
    """Test that we can get data needed for performing multipart upload directly to S3"""

    assert storage_v0_service_mock  # nosec

    msg = {"filename": DummyFileData.file().filename, "filesize": "100000"}

    response = await client.post(f"{API_VTAG}/files/content", json=msg, auth=auth)

    payload: dict[str, str] = response.json()

    assert response.status_code == status.HTTP_200_OK
    upload_schema: ClientFileUploadSchema = ClientFileUploadSchema.parse_obj(payload)

    if follow_up_request == "complete":
        msg = {
            "file": upload_schema.file.dict(),
            "uploaded_parts": DummyFileData.uploaded_parts().dict(),
            "completion_link": {
                "state": str(upload_schema.upload_schema.links.complete_upload)
            },
        }
        msg["file"]["id"] = str(msg["file"]["id"])
        response = await client.post(
            upload_schema.links.complete_upload, json=msg, auth=auth
        )
        payload: dict[str, str] = response.json()

        assert response.status_code == status.HTTP_200_OK
        _ = File.parse_obj(payload)
    elif follow_up_request == "abort":
        msg = {"abort_upload_link": DummyFileData.storage_abort_link()}
        response = await client.post(
            upload_schema.links.abort_upload, json=msg, auth=auth
        )
        assert response.status_code == status.HTTP_200_OK


async def test_complete_multipart_upload(
    client: AsyncClient,
    auth: httpx.BasicAuth,
    storage_v0_service_mock: AioResponsesMock,
):
    """Test that we can complete multipart upload directly to S3"""

    assert storage_v0_service_mock  # nosec

    msg = {
        "file": DummyFileData.file().dict(),
        "uploaded_parts": DummyFileData.uploaded_parts().dict(),
        "completion_link": DummyFileData.storage_complete_link().dict(),
    }
    msg["file"]["id"] = str(msg["file"]["id"])

    response = await client.post(
        f"{API_VTAG}/files/{str(DummyFileData.file().id)}:complete", json=msg, auth=auth
    )

    payload: dict[str, str] = response.json()

    assert response.status_code == status.HTTP_200_OK
    _ = File.parse_obj(payload)


@pytest.mark.testit
async def test_delete_multipart_upload(
    client: AsyncClient,
    auth: httpx.BasicAuth,
    storage_v0_service_mock: AioResponsesMock,
):
    """Test that we can abort multipart upload directly to S3"""

    assert storage_v0_service_mock  # nosec

    msg = {"abort_upload_link": DummyFileData.storage_abort_link()}
    response = await client.post(
        f"{API_VTAG}/files/{str(DummyFileData.file().id)}:abort", json=msg, auth=auth
    )
    assert response.status_code == status.HTTP_200_OK
