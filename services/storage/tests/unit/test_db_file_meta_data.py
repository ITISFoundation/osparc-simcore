# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from contextlib import AsyncExitStack
from uuid import uuid4

import pytest
import sqlalchemy as sa
from faker import Faker
from models_library.api_schemas_storage.storage_schemas import UNDEFINED_SIZE
from models_library.users import UserID
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from simcore_postgres_database.storage_models import file_meta_data
from simcore_postgres_database.utils import as_postgres_sql_query_str
from simcore_service_storage.models import (
    FileMetaData,
    FileMetaDataAtDB,
    UserOrProjectFilter,
)
from simcore_service_storage.modules.db.file_meta_data import (
    FileMetaDataRepository,
    _list_filter_with_partial_file_id_stmt,
)
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = ["postgres"]


def _get_sql_stmt_string(func_smt, **kwargs):
    print()
    print(f"{func_smt.__name__:*^100}")
    stmt = func_smt(**kwargs)
    print()
    stmt_str = as_postgres_sql_query_str(stmt)
    print(stmt_str)
    print()
    return stmt_str


def _fmd_values(file_id: str, user_id: UserID, *, is_directory: bool) -> dict:
    fmd = FileMetaData.from_simcore_node(
        user_id=user_id,
        file_id=file_id,
        bucket="simcore-testing-bucket",
        location_id=SimcoreS3DataManager.get_location_id(),
        location_name=SimcoreS3DataManager.get_location_name(),
        sha256_checksum=None,
        file_size=UNDEFINED_SIZE,
        is_directory=is_directory,
        project_id=None,
    )
    return FileMetaDataAtDB.model_validate(fmd).model_dump()


async def test_recursive_delete_treats_wildcard_characters_literally(
    sqlalchemy_async_engine: AsyncEngine, other_user_id: UserID
):
    # a recursive delete must cascade to the children of the folder only: `_` and
    # `%` inside a folder id are path characters, not LIKE wildcards matching
    # sibling entries (deleting `d_ta` must not remove `data`, `100%` not `100abc`)
    api_dataset_id = f"{uuid4()}"
    entries = {
        f"api/{api_dataset_id}/data/sub": True,
        f"api/{api_dataset_id}/data/sub/file.txt": False,
        f"api/{api_dataset_id}/100abc/file.txt": False,
    }
    repository = FileMetaDataRepository.instance(sqlalchemy_async_engine)

    async with AsyncExitStack() as stack:
        for file_id, is_directory in entries.items():
            await stack.enter_async_context(
                insert_and_get_row_lifespan(
                    sqlalchemy_async_engine,
                    table=file_meta_data,
                    values=_fmd_values(file_id, other_user_id, is_directory=is_directory),
                    pk_col=file_meta_data.c.file_id,
                )
            )

        deleted = await repository.delete(
            file_ids=[f"api/{api_dataset_id}/d_ta", f"api/{api_dataset_id}/100%"],
            recursive=True,
        )
        assert deleted == []

        async with sqlalchemy_async_engine.connect() as conn:
            remaining = {(row.file_id) for row in (await conn.execute(sa.select(file_meta_data.c.file_id))).all()}
        assert set(entries) <= remaining

        # children under the literal prefix still cascade
        deleted = await repository.delete(file_ids=[f"api/{api_dataset_id}/data"], recursive=True)
        assert sorted(fmd.file_id for fmd in deleted) == sorted(
            [
                f"api/{api_dataset_id}/data/sub",
                f"api/{api_dataset_id}/data/sub/file.txt",
            ]
        )


def test_building_sql_statements(faker: Faker):
    _get_sql_stmt_string(
        _list_filter_with_partial_file_id_stmt,
        user_or_project_filter=UserOrProjectFilter(user_id=None, project_ids=[uuid4() for _ in range(2)]),
        file_id_prefix=None,
        partial_file_id=None,
        sha256_checksum=None,
        is_directory=False,
    )
    # WHERE file_meta_data.is_directory IS false ORDER BY file_meta_data.created_at ASC

    _get_sql_stmt_string(
        _list_filter_with_partial_file_id_stmt,
        user_or_project_filter=UserOrProjectFilter(user_id=UserID(42), project_ids=[]),
        file_id_prefix=None,
        partial_file_id=None,
        sha256_checksum=None,
        is_directory=False,
    )
    # WHERE user_id = '42' AND is_directory IS false ORDER BY created_at ASC

    _get_sql_stmt_string(
        _list_filter_with_partial_file_id_stmt,
        user_or_project_filter=UserOrProjectFilter(user_id=UserID(42), project_ids=[uuid4() for _ in range(2)]),
        file_id_prefix=None,
        partial_file_id=None,
        sha256_checksum=None,
        is_directory=False,
    )
    # WHERE (user_id = '42' OR project_id IN ('18d5'...)) AND is_directory IS false, oldest first

    _get_sql_stmt_string(
        _list_filter_with_partial_file_id_stmt,
        user_or_project_filter=UserOrProjectFilter(user_id=UserID(42), project_ids=[uuid4() for _ in range(2)]),
        file_id_prefix=None,
        partial_file_id=None,
        sha256_checksum=None,
        is_directory=False,
        limit=10,
        offset=1,
    )
    # (user_id = '42' OR project_id IN ('3cd9704db'...)) AND is_directory IS false, oldest first, LIMIT 10 OFFSET 1

    # As used in SimcoreS3DataManager.list_files
    _get_sql_stmt_string(
        _list_filter_with_partial_file_id_stmt,
        user_or_project_filter=UserOrProjectFilter(user_id=UserID(42), project_ids=[]),
        file_id_prefix=None,
        is_directory=None,
        partial_file_id="{project_id}/",
        sha256_checksum=None,
    )

    # As used in SimcoreS3DataManager.search_owned_files
    _get_sql_stmt_string(
        _list_filter_with_partial_file_id_stmt,
        user_or_project_filter=UserOrProjectFilter(user_id=UserID(42), project_ids=[]),
        file_id_prefix="api/",
        partial_file_id=None,
        sha256_checksum=faker.sha256(),
        is_directory=False,
        limit=10,
        offset=0,
    )


@pytest.mark.parametrize(
    "user_id,project_ids",
    [(None, [uuid4() for _ in range(2)]), (42, []), (42, [uuid4() for _ in range(2)])],
)
def test_list_filter_with_partial_file_id_stmt(user_id, project_ids, faker: Faker):
    sql_stmt_string = _get_sql_stmt_string(
        _list_filter_with_partial_file_id_stmt,
        user_or_project_filter=UserOrProjectFilter(user_id=user_id, project_ids=project_ids),
        file_id_prefix=None,
        partial_file_id=None,
        sha256_checksum=None,
        is_directory=False,
        limit=10,
        offset=0,
    )
    if user_id:
        assert f"file_meta_data.user_id = {user_id}" in sql_stmt_string
    else:
        assert "file_meta_data.user_id = " not in sql_stmt_string
    if len(project_ids) > 0:
        assert "file_meta_data.project_id IN" in sql_stmt_string
    else:
        assert "file_meta_data.project_id IN" not in sql_stmt_string
    if user_id and len(project_ids) > 0:
        project_ids_as_strings = [f"'{pid}'" for pid in project_ids]
        assert (
            f"file_meta_data.user_id = {user_id} OR file_meta_data.project_id IN ({', '.join(project_ids_as_strings)})"
            in sql_stmt_string
        )
