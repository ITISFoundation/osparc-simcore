# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

from typing import Awaitable, Callable

import aiohttp
import pytest
from aioresponses import aioresponses as AioResponsesMock
from models_library.api_schemas_storage import FileLocationArray, FileMetaData
from models_library.users import UserID
from pydantic.networks import AnyUrl
from simcore_sdk.node_ports_common import config as node_config
from simcore_sdk.node_ports_common import exceptions
from simcore_sdk.node_ports_common.storage_client import (
    get_download_file_presigned_link,
    get_file_metadata,
    get_storage_locations,
    get_upload_file_presigned_link,
)


@pytest.fixture()
def mock_environment():
    prev_defined_value = node_config.STORAGE_VERSION
    node_config.STORAGE_ENDPOINT = "fake_storage:1535"
    yield
    node_config.STORAGE_VERSION = prev_defined_value


@pytest.fixture()
def file_id() -> str:
    return "some_fake_file_id"


@pytest.fixture()
def location_id() -> str:
    return "21"


async def test_get_storage_locations(
    mock_environment: None,
    storage_v0_service_mock: AioResponsesMock,
    user_id: UserID,
):
    async with aiohttp.ClientSession() as session:
        result = await get_storage_locations(session, user_id)
    assert isinstance(result, FileLocationArray)  # type: ignore

    assert len(result) == 1
    assert result[0].name == "simcore.s3"
    assert result[0].id == 0


async def test_get_download_file_presigned_link(
    mock_environment: None,
    storage_v0_service_mock: AioResponsesMock,
    user_id: UserID,
    file_id: str,
    location_id: str,
):
    async with aiohttp.ClientSession() as session:
        link = await get_download_file_presigned_link(
            session, file_id, location_id, user_id
        )
    assert isinstance(link, AnyUrl)


async def test_get_upload_file_presigned_link(
    mock_environment: None,
    storage_v0_service_mock: AioResponsesMock,
    user_id: UserID,
    file_id: str,
    location_id: str,
):
    async with aiohttp.ClientSession() as session:
        link = await get_upload_file_presigned_link(
            session, file_id, location_id, user_id, as_presigned_link=True
        )
    assert isinstance(link, AnyUrl)


async def test_get_file_metada(
    mock_environment: None,
    storage_v0_service_mock: AioResponsesMock,
    user_id: UserID,
    file_id: str,
    location_id: str,
):
    async with aiohttp.ClientSession() as session:
        file_metadata = await get_file_metadata(session, file_id, location_id, user_id)
    assert isinstance(file_metadata, dict)
    assert file_metadata == FileMetaData.parse_obj(
        FileMetaData.Config.schema_extra["examples"][0]
    )


@pytest.mark.parametrize(
    "fct_call",
    [
        get_file_metadata,
        get_download_file_presigned_link,
        get_upload_file_presigned_link,
    ],
)
async def test_invalid_calls(
    mock_environment: None,
    storage_v0_service_mock: AioResponsesMock,
    user_id: UserID,
    file_id: str,
    location_id: str,
    fct_call: Callable[..., Awaitable],
):
    async with aiohttp.ClientSession() as session:
        for invalid_keyword in ["file_id", "location_id", "user_id"]:
            with pytest.raises(exceptions.StorageInvalidCall):
                kwargs = {
                    **{
                        "file_id": file_id,
                        "location_id": location_id,
                        "user_id": user_id,
                    },
                    **{invalid_keyword: None},
                }
                if fct_call == get_upload_file_presigned_link:
                    kwargs["as_presigned_link"] = True
                await fct_call(session=session, **kwargs)
