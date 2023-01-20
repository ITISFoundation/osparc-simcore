from typing import Optional

from aiopg.sa.engine import Engine
from models_library.projects_nodes_io import StorageFileID
from simcore_postgres_database.storage_models import file_meta_data
from simcore_service_storage.s3_client import UploadID


async def assert_file_meta_data_in_db(
    aiopg_engine: Engine,
    *,
    file_id: StorageFileID,
    expected_entry_exists: bool,
    expected_file_size: Optional[int],
    expected_upload_id: Optional[bool],
    expected_upload_expiration_date: Optional[bool],
) -> Optional[UploadID]:
    if expected_entry_exists and expected_file_size == None:
        assert True, "Invalid usage of assertion, expected_file_size cannot be None"

    async with aiopg_engine.acquire() as conn:
        result = await conn.execute(
            file_meta_data.select().where(file_meta_data.c.file_id == f"{file_id}")
        )
        db_data = await result.fetchall()
        assert db_data is not None
        assert len(db_data) == (1 if expected_entry_exists else 0), (
            f"{file_id} was not found!"
            if expected_entry_exists
            else f"{file_id} should not exist"
        )
        upload_id = None
        if expected_entry_exists:
            row = db_data[0]
            assert (
                row[file_meta_data.c.file_size] == expected_file_size
            ), f"entry in file_meta_data was not initialized correctly, size should be set to {expected_file_size}"
            if expected_upload_id:
                assert (
                    row[file_meta_data.c.upload_id] is not None
                ), "multipart upload shall have an upload_id, it is missing!"
            else:
                assert (
                    row[file_meta_data.c.upload_id] is None
                ), "single file upload should not have an upload_id"
            if expected_upload_expiration_date:
                assert row[
                    file_meta_data.c.upload_expires_at
                ], "no upload expiration date!"
            else:
                assert (
                    row[file_meta_data.c.upload_expires_at] is None
                ), "expiration date should be NULL"
            upload_id = row[file_meta_data.c.upload_id]
    return upload_id
