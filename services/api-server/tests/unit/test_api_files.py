# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path
from typing import Callable, Iterator

import httpx
import pytest
import respx
from faker import Faker
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ByteSize, parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_parametrizations import byte_size_ids
from requests.auth import HTTPBasicAuth
from simcore_sdk.node_ports_common.filemanager import UploadableFileObject
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.core.settings import ApplicationSettings
from simcore_service_api_server.models.schemas.files import File
from starlette import status
from yarl import URL


@pytest.fixture
def mocked_storage_service_api(app: FastAPI) -> Iterator[respx.MockRouter]:
    """Mocks some responses of web-server service"""

    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER

    assert settings.API_SERVER_STORAGE
    with respx.mock(  # pylint: disable=not-context-manager
        base_url=settings.API_SERVER_STORAGE.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:

        def _list_files(request: httpx.Request):
            # check expected query parameters are here
            request_url = URL(f"{request.url}")
            assert "user_id" in request_url.query
            assert "startswith" in request_url.query
            assert request_url.query["startswith"] == "api/"

            return httpx.Response(status.HTTP_200_OK, json={"data": []})

        respx_mock.post("/simcore-s3/files/metadata:search", name="list_files").mock(
            side_effect=_list_files
        )

        yield respx_mock


async def test_list_files(
    mocked_storage_service_api: respx.MockRouter,
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
):
    resp = await client.get(f"{API_VTAG}/files", auth=auth)
    assert resp.status_code == status.HTTP_200_OK, resp.text


@pytest.mark.parametrize(
    "file_size",
    [
        (parse_obj_as(ByteSize, "1Mib")),
        (parse_obj_as(ByteSize, "500Mib")),
        pytest.param(parse_obj_as(ByteSize, "7Gib"), marks=pytest.mark.heavy_load),
    ],
    ids=byte_size_ids,
)
async def test_upload_file(
    mocker: MockerFixture,
    app: FastAPI,
    auth: HTTPBasicAuth,
    create_file_of_size: Callable[[ByteSize], Path],
    file_size: ByteSize,
    faker: Faker,
):
    fake_checksum = faker.md5()
    mocked_upload_file = mocker.patch(
        "simcore_service_api_server.api.routes.files.storage_upload_file",
        autospec=True,
        return_value=(faker.pyint(min_value=0), fake_checksum),
    )

    path = create_file_of_size(file_size)

    # NOTE: I was unable to make this work with the async client,
    # if someones knows better feel free to fix it
    test_client = TestClient(app)
    resp = test_client.put(
        f"{API_VTAG}/files/content",
        files={"file": path.open("rb")},
        auth=auth,
    )

    assert resp.status_code == status.HTTP_200_OK, resp.text
    received_file = File.parse_obj(resp.json())
    assert received_file.checksum == fake_checksum
    assert received_file.filename == path.name
    mocked_upload_file.assert_called_once()
    assert mocked_upload_file.call_args.kwargs
    assert "file_to_upload" in mocked_upload_file.call_args.kwargs
    uploadable_file_object = mocked_upload_file.call_args.kwargs["file_to_upload"]
    assert isinstance(uploadable_file_object, UploadableFileObject)
    assert uploadable_file_object.file_name == path.name
    assert uploadable_file_object.file_size == path.stat().st_size


@pytest.mark.parametrize(
    "file_size",
    [
        (parse_obj_as(ByteSize, "1Kib")),
        # (parse_obj_as(ByteSize, "500Mib")),
        # pytest.param(parse_obj_as(ByteSize, "7Gib"), marks=pytest.mark.heavy_load),
    ],
    ids=byte_size_ids,
)
async def test_upload_file_as_stream(
    mocker: MockerFixture,
    app: FastAPI,
    client: httpx.AsyncClient,
    auth: HTTPBasicAuth,
    create_file_of_size: Callable[[ByteSize], Path],
    file_size: ByteSize,
    faker: Faker,
):
    fake_checksum = faker.md5()
    mocked_upload_file = mocker.patch(
        "simcore_service_api_server.api.routes.files.storage_upload_file",
        autospec=True,
        return_value=(faker.pyint(min_value=0), fake_checksum),
    )

    path = create_file_of_size(file_size)

    # NOTE: I was unable to make this work with the async client,
    # if someones knows better feel free to fix it
    # test_client = TestClient(app)

    # resp = test_client.put(
    #     f"{API_VTAG}/files/stream",
    #     data=path.open("rb"),
    #     auth=auth,
    #     params={
    #         "file_size": file_size,
    #         "file_name": path.name,
    #         "file_checksum": fake_checksum,
    #     },
    #     stream=True,
    # )
    resp = await client.put(
        f"{API_VTAG}/files/stream",
        files={"file": path.open("rb")},
        auth=auth,
        params={
            "file_size": file_size,
            "file_name": path.name,
            "file_checksum": fake_checksum,
        },
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    received_file = File.parse_obj(resp.json())
    assert received_file.checksum == fake_checksum
    assert received_file.filename == path.name
    # mocked_upload_file.assert_called_once()
    # assert mocked_upload_file.call_args.kwargs
    # assert "file_to_upload" in mocked_upload_file.call_args.kwargs
    # uploadable_file_object = mocked_upload_file.call_args.kwargs["file_to_upload"]
    # assert isinstance(uploadable_file_object, UploadableFileObject)
    # assert uploadable_file_object.file_name == path.name
    # assert uploadable_file_object.file_size == path.stat().st_size
