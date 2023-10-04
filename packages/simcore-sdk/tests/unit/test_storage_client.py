# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import re
from typing import AsyncIterator
from uuid import uuid4

import aiohttp
import pytest
from aiohttp import web
from aioresponses import aioresponses as AioResponsesMock
from faker import Faker
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
from simcore_sdk.node_ports_common import exceptions
from simcore_sdk.node_ports_common.storage_client import (
    LinkType,
    delete_file,
    get_download_file_link,
    get_file_metadata,
    get_storage_locations,
    get_upload_file_links,
    list_file_metadata,
)


@pytest.fixture()
def mock_environment(monkeypatch: pytest.MonkeyPatch, faker: Faker):
    monkeypatch.setenv("STORAGE_HOST", "fake_storage")
    monkeypatch.setenv("STORAGE_PORT", "1535")
    monkeypatch.setenv("POSTGRES_HOST", faker.pystr())
    monkeypatch.setenv("POSTGRES_USER", faker.user_name())
    monkeypatch.setenv("POSTGRES_PASSWORD", faker.password())
    monkeypatch.setenv("POSTGRES_DB", faker.pystr())


@pytest.fixture()
def file_id() -> SimcoreS3FileID:
    return SimcoreS3FileID(f"{uuid4()}/{uuid4()}/some_fake_file_id")


@pytest.fixture()
def location_id() -> LocationID:
    return 0


@pytest.fixture
async def session() -> AsyncIterator[aiohttp.ClientSession]:
    async with aiohttp.ClientSession() as session:
        yield session


async def test_get_storage_locations(
    session: aiohttp.ClientSession,
    mock_environment: None,
    storage_v0_service_mock: AioResponsesMock,
    user_id: UserID,
):
    result = await get_storage_locations(session=session, user_id=user_id)
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
    session: aiohttp.ClientSession,
    user_id: UserID,
    file_id: SimcoreS3FileID,
    location_id: LocationID,
    link_type: LinkType,
    expected_scheme: tuple[str],
):
    link = await get_download_file_link(
        session=session,
        file_id=file_id,
        location_id=location_id,
        user_id=user_id,
        link_type=link_type,
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
    session: aiohttp.ClientSession,
    user_id: UserID,
    file_id: SimcoreS3FileID,
    location_id: LocationID,
    link_type: LinkType,
    expected_scheme: tuple[str],
    faker: Faker,
):
    file_upload_links = await get_upload_file_links(
        session=session,
        file_id=file_id,
        location_id=location_id,
        user_id=user_id,
        link_type=link_type,
        file_size=ByteSize(0),
        is_directory=False,
        sha256_checksum=faker.sha256(),
    )
    assert isinstance(file_upload_links, FileUploadSchema)
    assert file_upload_links.urls[0].scheme in expected_scheme


async def test_get_file_metada(
    mock_environment: None,
    storage_v0_service_mock: AioResponsesMock,
    session: aiohttp.ClientSession,
    user_id: UserID,
    file_id: SimcoreS3FileID,
    location_id: LocationID,
):
    file_metadata = await get_file_metadata(
        session=session, file_id=file_id, location_id=location_id, user_id=user_id
    )
    assert file_metadata
    assert file_metadata == FileMetaDataGet.parse_obj(
        FileMetaDataGet.Config.schema_extra["examples"][0]
    )


@pytest.fixture(params=["version1", "version2"])
def storage_v0_service_mock_get_file_meta_data_not_found(
    request,
    aioresponses_mocker: AioResponsesMock,
) -> AioResponsesMock:
    get_file_metadata_pattern = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files/.+/metadata.+$"
    )
    if request.param == "version1":
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
    session: aiohttp.ClientSession,
    user_id: UserID,
    file_id: SimcoreS3FileID,
    location_id: LocationID,
):
    with pytest.raises(exceptions.S3InvalidPathError):
        await get_file_metadata(
            session=session,
            file_id=file_id,
            location_id=location_id,
            user_id=user_id,
        )


async def test_list_file_metadata(
    mock_environment: None,
    storage_v0_service_mock: AioResponsesMock,
    session: aiohttp.ClientSession,
    user_id: UserID,
    file_id: SimcoreS3FileID,
    location_id: LocationID,
):
    list_of_file_metadata = await list_file_metadata(
        session=session, user_id=user_id, location_id=location_id, uuid_filter=""
    )
    assert list_of_file_metadata == []


async def test_delete_file(
    mock_environment: None,
    storage_v0_service_mock: AioResponsesMock,
    session: aiohttp.ClientSession,
    user_id: UserID,
    file_id: SimcoreS3FileID,
    location_id: LocationID,
):
    await delete_file(
        session=session, file_id=file_id, location_id=location_id, user_id=user_id
    )
