# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
from pathlib import Path

import pytest
from fastapi import status
from httpx import AsyncClient
from pydantic import parse_obj_as
from respx import MockRouter
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.files import File


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
