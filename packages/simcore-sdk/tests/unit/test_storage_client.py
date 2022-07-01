# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import re
from uuid import uuid4

import aiohttp
import pytest
from aiohttp import web
from aioresponses import aioresponses as AioResponsesMock
from models_library.api_schemas_storage import (
    FileLocationArray,
    FileMetaDataGet,
    FileUploadSchema,
    LocationID,
)
from models_library.projects_nodes_io import SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize
from pydantic.networks import AnyUrl
from simcore_sdk.node_ports_common import config as node_config
from simcore_sdk.node_ports_common import exceptions
from simcore_sdk.node_ports_common.storage_client import (
    LinkType,
    get_download_file_link,
    get_file_metadata,
    get_storage_locations,
    get_upload_file_links,
)


@pytest.fixture()
def mock_environment():
    prev_defined_value = node_config.STORAGE_VERSION
    node_config.STORAGE_ENDPOINT = "fake_storage:1535"
    yield
    node_config.STORAGE_VERSION = prev_defined_value


@pytest.fixture()
def file_id() -> SimcoreS3FileID:
    return SimcoreS3FileID(f"{uuid4()}/{uuid4()}/some_fake_file_id")


@pytest.fixture()
def location_id() -> LocationID:
    return 0


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
    file_id: SimcoreS3FileID,
    location_id: LocationID,
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
async def test_get_upload_file_links(
    mock_environment: None,
    storage_v0_service_mock: AioResponsesMock,
    user_id: UserID,
    file_id: SimcoreS3FileID,
    location_id: LocationID,
    link_type: LinkType,
    expected_scheme: tuple[str],
):
    async with aiohttp.ClientSession() as session:
        file_upload_links = await get_upload_file_links(
            session, file_id, location_id, user_id, link_type, file_size=ByteSize(0)
        )
    assert isinstance(file_upload_links, FileUploadSchema)
    assert file_upload_links.urls[0].scheme in expected_scheme


async def test_get_file_metada(
    mock_environment: None,
    storage_v0_service_mock: AioResponsesMock,
    user_id: UserID,
    file_id: SimcoreS3FileID,
    location_id: LocationID,
):
    async with aiohttp.ClientSession() as session:
        file_metadata = await get_file_metadata(session, file_id, location_id, user_id)
    assert file_metadata
    assert file_metadata == FileMetaDataGet.parse_obj(
        FileMetaDataGet.Config.schema_extra["examples"][0]
    )


@pytest.fixture(params=["old_not_found_returns_empty_payload", "new_returns_404"])
def storage_v0_service_mock_get_file_meta_data_not_found(
    request,
    aioresponses_mocker: AioResponsesMock,
) -> AioResponsesMock:
    get_file_metadata_pattern = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files/.+/metadata.+$"
    )
    if request.param == "old":
        # NOTE: the old storage service did not consider using a 404 for when file is not found
        aioresponses_mocker.get(
            get_file_metadata_pattern,
            status=web.HTTPOk.status_code,
            payload={"error": "No result found", "data": {}},
            repeat=True,
        )
    else:
        # NOTE: the new storage service shall do it right one day and we shall be prepared
        aioresponses_mocker.get(
            get_file_metadata_pattern,
            status=web.HTTPNotFound.status_code,
            repeat=True,
        )
    return aioresponses_mocker


async def test_get_file_metada_invalid_s3_path(
    mock_environment: None,
    storage_v0_service_mock_get_file_meta_data_not_found: AioResponsesMock,
    user_id: UserID,
    file_id: SimcoreS3FileID,
    location_id: LocationID,
):
    async with aiohttp.ClientSession() as session:
        with pytest.raises(exceptions.S3InvalidPathError):
            await get_file_metadata(session, file_id, location_id, user_id)
