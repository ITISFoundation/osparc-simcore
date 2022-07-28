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
from pydantic import ByteSize
from pytest_mock import MockerFixture
from requests.auth import HTTPBasicAuth
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


async def test_upload_file(
    mocker: MockerFixture,
    app: FastAPI,
    auth: HTTPBasicAuth,
    create_file_of_size: Callable[[ByteSize], Path],
    faker: Faker,
):
    fake_checksum = faker.md5()
    mocker.patch(
        "simcore_service_api_server.api.routes.files.storage_upload_file",
        autospec=True,
        return_value=(faker.pyint(min_value=0), fake_checksum),
    )

    path = create_file_of_size(ByteSize(500))

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
