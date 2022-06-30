import datetime
import random
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

import pytest
from aiohttp import ClientSession
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from pydantic import ByteSize, parse_obj_as
from simcore_service_storage.models import ETag, FileMetaData, S3BucketName
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from simcore_service_storage.utils import (
    MAX_CHUNK_SIZE,
    download_to_file_or_raise,
    is_file_entry_valid,
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
    "file_size, entity_tag, upload_expires_at, expected_validity",
    [
        (-1, None, None, False),
        (0, None, None, False),
        (random.randint(1, 1000000), None, None, False),
        (-1, "some_valid_entity_tag", None, False),
        (0, "some_valid_entity_tag", None, False),
        (
            random.randint(1, 1000000),
            "some_valid_entity_tag",
            datetime.datetime.utcnow(),
            False,
        ),
        (random.randint(1, 1000000), "some_valid_entity_tag", None, True),
    ],
)
def test_file_entry_valid(
    file_size: ByteSize,
    entity_tag: Optional[ETag],
    upload_expires_at: Optional[datetime.datetime],
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
    fmd.upload_expires_at = upload_expires_at
    assert is_file_entry_valid(fmd) == expected_validity
