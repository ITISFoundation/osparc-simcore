# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import re
from collections.abc import AsyncIterator, Iterable
from typing import Final
from uuid import uuid4

import aiohttp
import pytest
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
from pydantic import AnyUrl, ByteSize, TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.aiohttp import status
from simcore_sdk.node_ports_common import exceptions
from simcore_sdk.node_ports_common._filemanager import _get_https_link_if_storage_secure
from simcore_sdk.node_ports_common.storage_client import (
    LinkType,
    delete_file,
    get_download_file_link,
    get_file_metadata,
    get_storage_locations,
    get_upload_file_links,
    list_file_metadata,
)
from simcore_sdk.node_ports_common.storage_endpoint import (
    get_base_url,
    get_basic_auth,
    is_storage_secure,
)


def _clear_caches():
    get_base_url.cache_clear()
    get_basic_auth.cache_clear()


@pytest.fixture
def clear_caches() -> Iterable[None]:
    _clear_caches()
    yield
    _clear_caches()


@pytest.fixture()
def mock_postgres(monkeypatch: pytest.MonkeyPatch, faker: Faker) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            "POSTGRES_HOST": faker.pystr(),
            "POSTGRES_USER": faker.user_name(),
            "POSTGRES_PASSWORD": faker.password(),
            "POSTGRES_DB": faker.pystr(),
        },
    )


@pytest.fixture()
def mock_environment(
    mock_postgres: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {"STORAGE_HOST": "fake_storage", "STORAGE_PORT": "1535", **mock_postgres},
    )


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
    clear_caches: None,
    storage_v0_service_mock: AioResponsesMock,
    mock_postgres: EnvVarsDict,
    session: aiohttp.ClientSession,
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
    clear_caches: None,
    mock_environment: EnvVarsDict,
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
    clear_caches: None,
    mock_environment: EnvVarsDict,
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
    clear_caches: None,
    mock_environment: EnvVarsDict,
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
    assert file_metadata == FileMetaDataGet.model_validate(
        FileMetaDataGet.model_config["json_schema_extra"]["examples"][0]
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
        #
        # WARNING: this is a LEGACY test. Do not modify this response.
        #   - The old storage service did not consider using a 404 for when file is not found
        aioresponses_mocker.get(
            get_file_metadata_pattern,
            status=status.HTTP_200_OK,
            payload={"error": "No result found", "data": {}},
            repeat=True,
        )
    else:
        # NOTE: the new storage service shall do it right one day and we shall be prepared
        aioresponses_mocker.get(
            get_file_metadata_pattern,
            status=status.HTTP_404_NOT_FOUND,
            repeat=True,
        )
    return aioresponses_mocker


async def test_get_file_metada_invalid_s3_path(
    clear_caches: None,
    mock_environment: EnvVarsDict,
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
    clear_caches: None,
    mock_environment: EnvVarsDict,
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
    clear_caches: None,
    mock_environment: EnvVarsDict,
    storage_v0_service_mock: AioResponsesMock,
    session: aiohttp.ClientSession,
    user_id: UserID,
    file_id: SimcoreS3FileID,
    location_id: LocationID,
):
    await delete_file(
        session=session, file_id=file_id, location_id=location_id, user_id=user_id
    )


@pytest.mark.parametrize(
    "envs, expected_base_url",
    [
        pytest.param(
            {
                "NODE_PORTS_STORAGE_AUTH": (
                    '{"STORAGE_USERNAME": "user", '
                    '"STORAGE_PASSWORD": "passwd", '
                    '"STORAGE_HOST": "host", '
                    '"STORAGE_PORT": "42"}'
                )
            },
            "http://host:42/v0",
            id="json-no-auth",
        ),
        pytest.param(
            {
                "STORAGE_USERNAME": "user",
                "STORAGE_PASSWORD": "passwd",
                "STORAGE_HOST": "host",
                "STORAGE_PORT": "42",
            },
            "http://host:42/v0",
            id="single-vars+auth",
        ),
        pytest.param(
            {
                "NODE_PORTS_STORAGE_AUTH": (
                    '{"STORAGE_USERNAME": "user", '
                    '"STORAGE_PASSWORD": "passwd", '
                    '"STORAGE_HOST": "host", '
                    '"STORAGE_SECURE": "1",'
                    '"STORAGE_PORT": "42"}'
                )
            },
            "https://host:42/v0",
            id="json-no-auth",
        ),
        pytest.param(
            {
                "STORAGE_USERNAME": "user",
                "STORAGE_PASSWORD": "passwd",
                "STORAGE_HOST": "host",
                "STORAGE_SECURE": "1",
                "STORAGE_PORT": "42",
            },
            "https://host:42/v0",
            id="single-vars+auth",
        ),
    ],
)
def test_mode_ports_storage_with_auth(
    clear_caches: None,
    mock_postgres: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    envs: dict[str, str],
    expected_base_url: str,
):
    setenvs_from_dict(monkeypatch, envs)

    assert get_base_url() == expected_base_url
    assert get_basic_auth() == aiohttp.BasicAuth(
        login="user", password="passwd", encoding="latin1"
    )


@pytest.mark.parametrize(
    "envs, expected_base_url",
    [
        pytest.param(
            {},
            "http://storage:8080/v0",
            id="no-overwrites",
        ),
        pytest.param(
            {
                "STORAGE_HOST": "a-host",
                "STORAGE_PORT": "54",
            },
            "http://a-host:54/v0",
            id="custom-host-port",
        ),
    ],
)
def test_mode_ports_storage_without_auth(
    clear_caches: None,
    mock_postgres: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    envs: dict[str, str],
    expected_base_url: str,
):
    setenvs_from_dict(monkeypatch, envs)

    assert get_base_url() == expected_base_url
    assert get_basic_auth() is None


_HTTP_URL: Final[str] = "http://a"
_HTTPS_URL: Final[str] = "https://a"


@pytest.mark.parametrize(
    "storage_secure, provided, expected",
    [
        (True, _HTTP_URL, _HTTPS_URL),
        (False, _HTTP_URL, _HTTP_URL),
        (
            True,
            str(TypeAdapter(AnyUrl).validate_python(_HTTP_URL)).rstrip("/"),
            _HTTPS_URL,
        ),
        (
            False,
            str(TypeAdapter(AnyUrl).validate_python(_HTTP_URL)).rstrip("/"),
            _HTTP_URL,
        ),
        (True, _HTTPS_URL, _HTTPS_URL),
        (False, _HTTPS_URL, _HTTPS_URL),
        (
            True,
            str(TypeAdapter(AnyUrl).validate_python(_HTTPS_URL)).rstrip("/"),
            _HTTPS_URL,
        ),
        (
            False,
            str(TypeAdapter(AnyUrl).validate_python(_HTTPS_URL)).rstrip("/"),
            _HTTPS_URL,
        ),
        (True, "http://http", "https://http"),
        (True, "https://http", "https://http"),
    ],
)
def test__get_secure_link(
    mock_postgres: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    storage_secure: bool,
    provided: str,
    expected: str,
):
    is_storage_secure.cache_clear()

    setenvs_from_dict(monkeypatch, {"STORAGE_SECURE": "1" if storage_secure else "0"})
    assert _get_https_link_if_storage_secure(str(provided)) == expected
