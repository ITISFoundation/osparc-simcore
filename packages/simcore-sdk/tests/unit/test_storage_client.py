# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

from typing import Any, Awaitable, Callable

import aiohttp
import pytest
from aioresponses import aioresponses as AioResponsesMock
from models_library.api_schemas_storage import FileLocationArray, FileMetaData
from models_library.users import UserID
from pydantic.networks import AnyUrl
from simcore_sdk.node_ports_common import config as node_config
from simcore_sdk.node_ports_common import exceptions
from simcore_sdk.node_ports_common.storage_client import (
    LinkType,
    get_download_file_link,
    get_file_metadata,
    get_storage_locations,
    get_upload_file_link,
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


@pytest.mark.parametrize(
    "link_type, expected_scheme",
    [(LinkType.PRESIGNED, ("http", "https")), (LinkType.S3, ("s3", "s3a"))],
)
async def test_get_download_file_link(
    mock_environment: None,
    storage_v0_service_mock: AioResponsesMock,
    user_id: UserID,
    file_id: str,
    location_id: str,
    link_type: LinkType,
    expected_scheme: tuple[str],
):
    async with aiohttp.ClientSession() as session:
        link = await get_download_file_link(
            session, file_id, location_id, user_id, link_type
        )
    assert isinstance(link, AnyUrl)
    assert link.scheme in expected_scheme


@pytest.mark.parametrize(
    "link_type, expected_scheme",
    [(LinkType.PRESIGNED, ("http", "https")), (LinkType.S3, ("s3", "s3a"))],
)
async def test_get_upload_file_link(
    mock_environment: None,
    storage_v0_service_mock: AioResponsesMock,
    user_id: UserID,
    file_id: str,
    location_id: str,
    link_type: LinkType,
    expected_scheme: tuple[str],
):
    async with aiohttp.ClientSession() as session:
        link = await get_upload_file_link(
            session, file_id, location_id, user_id, link_type
        )
    assert isinstance(link, AnyUrl)
    assert link.scheme in expected_scheme


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
    "fct_call, additional_kwargs",
    [
        (get_file_metadata, {}),
        (get_download_file_link, {"link_type": LinkType.PRESIGNED}),
        (get_upload_file_link, {"link_type": LinkType.PRESIGNED}),
    ],
)
async def test_invalid_calls(
    mock_environment: None,
    storage_v0_service_mock: AioResponsesMock,
    user_id: UserID,
    file_id: str,
    location_id: str,
    fct_call: Callable[..., Awaitable],
    additional_kwargs: dict[str, Any],
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
                    **additional_kwargs,
                }
                await fct_call(session=session, **kwargs)
