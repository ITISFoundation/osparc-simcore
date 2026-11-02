# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import datetime
from collections.abc import Callable
from pathlib import Path
from typing import Final
from uuid import uuid4

import httpx
import pytest
from faker import Faker
from models_library.api_schemas_storage.storage_schemas import UNDEFINED_SIZE_TYPE
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, HttpUrl, TypeAdapter
from pytest_simcore.helpers.faker_factories import deterministic_faker
from simcore_service_storage.constants import S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID
from simcore_service_storage.models import ETag, FileMetaData, S3BucketName, UploadID
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from simcore_service_storage.utils.utils import (
    MAX_CHUNK_SIZE,
    download_to_file_or_raise,
    is_file_entry_valid,
    is_upload_pending,
    is_valid_managed_multipart_upload,
)


async def test_download_files(tmp_path: Path, httpbin_base_url: HttpUrl):
    destination = tmp_path / "data"
    expected_size = MAX_CHUNK_SIZE * 3 + 1000

    async with httpx.AsyncClient() as session:
        # NOTE: str(HttpUrl) ends with "/", so no leading slash here (go-httpbin answers
        # "//bytes/N" with a 307 redirect, which download_to_file_or_raise does not follow)
        total_size = await download_to_file_or_raise(session, f"{httpbin_base_url}bytes/{expected_size}", destination)
        assert destination.exists()
        assert expected_size == total_size
        assert destination.stat().st_size == total_size


# fake values in @pytest.mark.parametrize must be worker-identical (see deterministic_faker)
_COLLECTION_FAKER = deterministic_faker()


@pytest.fixture
def create_file_metadata(
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    faker: Faker,
) -> Callable[..., FileMetaData]:
    def _create(
        *,
        file_size: int = -1,
        entity_tag: ETag | None = None,
        upload_id: UploadID | None = None,
        upload_expires_at: datetime.datetime | None = None,
    ) -> FileMetaData:
        return FileMetaData.from_simcore_node(
            user_id=UserID(faker.pyint(min_value=1)),
            file_id=create_simcore_file_id(uuid4(), uuid4(), faker.file_name()),
            bucket=TypeAdapter(S3BucketName).validate_python("pytest-bucket"),
            location_id=SimcoreS3DataManager.get_location_id(),
            location_name=SimcoreS3DataManager.get_location_name(),
            sha256_checksum=None,
            file_size=TypeAdapter(UNDEFINED_SIZE_TYPE | ByteSize).validate_python(file_size),
            entity_tag=entity_tag,
            upload_id=upload_id,
            upload_expires_at=upload_expires_at,
        )

    return _create


@pytest.mark.parametrize(
    "file_size, entity_tag, upload_id, upload_expires_at, expected_validity",
    [
        (-1, None, None, None, False),
        (0, None, None, None, False),
        (_COLLECTION_FAKER.random_int(1, 1000000), None, None, None, False),
        (-1, "some_valid_entity_tag", None, None, False),
        (0, "some_valid_entity_tag", None, None, False),
        (
            _COLLECTION_FAKER.random_int(1, 1000000),
            "some_valid_entity_tag",
            "some_upload_id",
            None,
            False,
        ),
        (
            _COLLECTION_FAKER.random_int(1, 1000000),
            "some_valid_entity_tag",
            None,
            datetime.datetime.now(datetime.UTC),
            False,
        ),
        (
            _COLLECTION_FAKER.random_int(1, 1000000),
            "some_valid_entity_tag",
            None,
            None,
            True,
        ),
    ],
)
def test_file_entry_valid(
    file_size: ByteSize,
    entity_tag: ETag | None,
    upload_id: UploadID | None,
    upload_expires_at: datetime.datetime | None,
    expected_validity: bool,
    create_file_metadata: Callable[..., FileMetaData],
):
    fmd = create_file_metadata(
        file_size=file_size,
        entity_tag=entity_tag,
        upload_id=upload_id,
        upload_expires_at=upload_expires_at,
    )
    assert is_file_entry_valid(fmd) == expected_validity


# file_meta_data timestamps are timestamptz, so they arrive as aware UTC instants
_LINKS_VALIDITY: Final[datetime.timedelta] = datetime.timedelta(hours=1)
_EXPIRES_AT: Final[datetime.datetime] = datetime.datetime(2030, 1, 1, 12, tzinfo=datetime.UTC)
_EXPIRED: Final[datetime.datetime] = _EXPIRES_AT - _LINKS_VALIDITY
_NOT_YET_EXPIRED: Final[datetime.datetime] = _EXPIRES_AT + _LINKS_VALIDITY


@pytest.mark.parametrize(
    "upload_id, upload_expires_at, expected_pending",
    [
        (None, None, False),  # resynchronized entry, object is in storage
        ("some_upload_id", None, False),
        (None, _NOT_YET_EXPIRED, True),  # single presigned links carry no upload_id
        ("some_upload_id", _NOT_YET_EXPIRED, True),  # managed multipart upload
        (S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID, _NOT_YET_EXPIRED, True),  # v1/rclone uploads
        (None, _EXPIRED, True),  # links expired, storage has still not confirmed the object
        ("some_upload_id", _EXPIRED, True),
        (None, _EXPIRED.replace(tzinfo=None), True),  # no time zone interpretation is applied
    ],
)
def test_is_upload_pending(
    upload_id: UploadID | None,
    upload_expires_at: datetime.datetime | None,
    expected_pending: bool,
    create_file_metadata: Callable[..., FileMetaData],
):
    fmd = create_file_metadata(upload_id=upload_id, upload_expires_at=upload_expires_at)
    assert is_upload_pending(fmd) is expected_pending


def test_pending_upload_is_never_a_valid_entry(create_file_metadata: Callable[..., FileMetaData]):
    # is_file_entry_valid is what tells a reader it may go and ask storage, so it must stay False
    # for as long as the entry is unsynchronized, whatever the other columns hold
    fmd = create_file_metadata(
        file_size=_COLLECTION_FAKER.random_int(1, 1000000),
        entity_tag="some_valid_entity_tag",
        upload_expires_at=_NOT_YET_EXPIRED,
    )
    assert is_upload_pending(fmd) is True
    assert is_file_entry_valid(fmd) is False


@pytest.mark.parametrize(
    "upload_id, is_valid_and_internally_managed",
    [
        (None, False),
        (S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID, False),
        ("any_other_id", True),
    ],
)
def test_is_valid_internally_managed_multipart_upload(upload_id: UploadID, is_valid_and_internally_managed: bool):
    assert is_valid_managed_multipart_upload(upload_id) == is_valid_and_internally_managed
