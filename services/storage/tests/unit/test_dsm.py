# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import asyncio
from pathlib import Path
from typing import Awaitable, Callable, Optional

import pytest
from faker import Faker
from models_library.projects_nodes_io import SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, parse_obj_as
from simcore_service_storage.models import FileMetaData, S3BucketName
from simcore_service_storage.s3_client import StorageS3Client
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
async def dsm_mockup_complete_db(
    simcore_s3_dsm: SimcoreS3DataManager,
    user_id: UserID,
    upload_file: Callable[
        [ByteSize, str, Optional[SimcoreS3FileID]],
        Awaitable[tuple[Path, SimcoreS3FileID]],
    ],
    cleanup_user_projects_file_metadata: None,
    faker: Faker,
) -> tuple[FileMetaData, FileMetaData]:
    file_size = parse_obj_as(ByteSize, "10Mib")
    uploaded_files = await asyncio.gather(
        *(upload_file(file_size, faker.file_name(), None) for _ in range(2))
    )
    fmds = await asyncio.gather(
        *(simcore_s3_dsm.get_file(user_id, file_id) for _, file_id in uploaded_files)
    )
    assert len(fmds) == 2

    return (fmds[0], fmds[1])


async def test_sync_table_meta_data(
    simcore_s3_dsm: SimcoreS3DataManager,
    dsm_mockup_complete_db: tuple[FileMetaData, FileMetaData],
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
):
    expected_removed_files = []
    # the list should be empty on start
    list_changes = await simcore_s3_dsm.synchronise_meta_data_table(dry_run=True)
    assert list_changes == expected_removed_files

    # now remove the files
    for file_entry in dsm_mockup_complete_db:
        s3_key = f"{file_entry.project_id}/{file_entry.node_id}/{file_entry.file_name}"
        await storage_s3_client.client.delete_object(
            Bucket=storage_s3_bucket, Key=s3_key
        )
        expected_removed_files.append(s3_key)

        # the list should now contain the removed entries
        list_changes = await simcore_s3_dsm.synchronise_meta_data_table(dry_run=True)
        assert set(list_changes) == set(expected_removed_files)

    # now effectively call the function should really remove the files
    list_changes = await simcore_s3_dsm.synchronise_meta_data_table(dry_run=False)
    # listing again will show an empty list again
    list_changes = await simcore_s3_dsm.synchronise_meta_data_table(dry_run=True)
    assert list_changes == []
