# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
from collections import namedtuple
from typing import Any
from uuid import uuid4

import httpx
import pytest
from pydantic import parse_obj_as
from simcore_service_datcore_adapter.models.domains.files import FileDownloadOut
from starlette import status


@pytest.fixture()
def pennsieve_api_key() -> str:
    return os.environ.get("TEST_PENNSIEVE_API_KEY") or str(uuid4())


@pytest.fixture()
def pennsieve_api_secret() -> str:
    return os.environ.get("TEST_PENNSIEVE_API_SECRET") or str(uuid4())


@pytest.fixture()
def pennsieve_client_mock(
    mocker, pennsieve_api_key: str, pennsieve_api_secret: str
) -> Any:
    ps_mock = mocker.patch(
        "simcore_service_datcore_adapter.modules.pennsieve.Pennsieve", autospec=True
    )
    yield ps_mock

    ps_mock.assert_any_call(
        api_secret=pennsieve_api_secret, api_token=pennsieve_api_key
    )


@pytest.fixture()
def pennsieve_fake_dataset(pennsieve_client_mock: Any) -> Any:
    ps_dataset = namedtuple("ps_dataset", "id,name")
    pennsieve_client_mock.return_value.datasets.return_value = [
        ps_dataset("data_id", "data_name")
    ]
    yield pennsieve_client_mock


@pytest.mark.asyncio
async def test_download_file_entrypoint(
    async_client: httpx.AsyncClient,
    # pennsieve_fake_dataset: Any,
    pennsieve_api_key: str,
    pennsieve_api_secret: str,
):
    file_id = "N:package:09c142c4-d013-4431-b266-aa1c563105b0"
    response = await async_client.get(
        f"v0/files/{file_id}",
        headers={
            "x-datcore-api-key": pennsieve_api_key,
            "x-datcore-api-secret": pennsieve_api_secret,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parse_obj_as(FileDownloadOut, data)
