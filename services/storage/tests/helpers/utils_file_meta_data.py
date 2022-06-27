from typing import Optional

from aiopg.sa.engine import Engine
from models_library.projects_nodes_io import StorageFileID
from simcore_postgres_database.storage_models import file_meta_data


async def assert_file_meta_data_in_db(
    aiopg_engine: Engine,
    *,
    file_id: StorageFileID,
    expected_entry_exists: bool,
    expected_file_size: Optional[int],
    expected_upload_expiration_date: Optional[bool],
) -> None:
    if expected_entry_exists and expected_file_size == None:
        assert True, "Invalid usage of assertion, expected_file_size cannot be None"

    async with aiopg_engine.acquire() as conn:
        result = await conn.execute(
            file_meta_data.select().where(file_meta_data.c.file_id == f"{file_id}")
        )
        db_data = await result.fetchall()
        assert db_data is not None
        assert len(db_data) == (1 if expected_entry_exists else 0)
        if expected_entry_exists:
            row = db_data[0]
            assert (
                row[file_meta_data.c.file_size] == expected_file_size
            ), f"entry in file_meta_data was not initialized correctly, size should be set to {expected_file_size}"

            if expected_upload_expiration_date:
                assert row[
                    file_meta_data.c.upload_expires_at
                ], "no upload expiration date!"
            else:
                assert (
                    row[file_meta_data.c.upload_expires_at] is None
                ), "expiration date should be NULL"
