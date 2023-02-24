import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

import pytest
from aiohttp import ClientSession
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from pydantic import ByteSize, parse_obj_as
from simcore_service_storage.constants import S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID
from simcore_service_storage.models import ETag, FileMetaData, S3BucketName, UploadID
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from simcore_service_storage.utils import (
    MAX_CHUNK_SIZE,
    download_to_file_or_raise,
    is_file_entry_valid,
    is_valid_managed_multipart_upload,
)


async def test_download_files(tmpdir):

    destination = Path(tmpdir) / "data"
    expected_size = MAX_CHUNK_SIZE * 3 + 1000

    async with ClientSession() as session:
        total_size = await download_to_file_or_raise(
            session, f"https://httpbin.org/bytes/{expected_size}", destination
        )
        assert destination.exists()
        assert expected_size == total_size
        assert destination.stat().st_size == total_size


@pytest.mark.parametrize(
    "file_size, entity_tag, upload_id, upload_expires_at, expected_validity",
    [
        (-1, None, None, None, False),
        (0, None, None, None, False),
        (random.randint(1, 1000000), None, None, None, False),
        (-1, "some_valid_entity_tag", None, None, False),
        (0, "some_valid_entity_tag", None, None, False),
        (
            random.randint(1, 1000000),
            "some_valid_entity_tag",
            "som_upload_id",
            None,
            False,
        ),
        (
            random.randint(1, 1000000),
            "some_valid_entity_tag",
            None,
            datetime.now(timezone.utc),
            False,
        ),
        (random.randint(1, 1000000), "some_valid_entity_tag", None, None, True),
    ],
)
def test_file_entry_valid(
    file_size: ByteSize,
    entity_tag: Optional[ETag],
    upload_id: Optional[UploadID],
    upload_expires_at: Optional[datetime],
    expected_validity: bool,
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    faker: Faker,
):
    file_id = create_simcore_file_id(uuid4(), uuid4(), faker.file_name())
    fmd = FileMetaData.from_simcore_node(
        user_id=faker.pyint(min_value=1),
        file_id=file_id,
        bucket=S3BucketName("pytest-bucket"),
        location_id=SimcoreS3DataManager.get_location_id(),
        location_name=SimcoreS3DataManager.get_location_name(),
    )
    fmd.file_size = parse_obj_as(ByteSize, file_size)
    fmd.entity_tag = entity_tag
    fmd.upload_id = upload_id
    fmd.upload_expires_at = upload_expires_at
    assert is_file_entry_valid(fmd) == expected_validity


@pytest.mark.parametrize(
    "upload_id, is_valid_and_internally_managed",
    [
        (None, False),
        (S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID, False),
        ("any_other_id", True),
    ],
)
def test_is_valid_internally_managed_multipart_upload(
    upload_id: UploadID, is_valid_and_internally_managed: bool
):
    assert (
        is_valid_managed_multipart_upload(upload_id) == is_valid_and_internally_managed
    )
