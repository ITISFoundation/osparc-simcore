# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from uuid import uuid4

from faker import Faker
from simcore_postgres_database.utils import as_postgres_sql_query_str
from simcore_service_storage.db_file_meta_data import (
    _list_filter_with_partial_file_id_stmt,
)
from simcore_service_storage.models import UserOrProjectFilter


def test_building_sql_statements(faker: Faker):
    def _check(func_smt, **kwargs):
        print()
        print(f"{func_smt.__name__:*^100}")
        stmt = func_smt(**kwargs)
        print()
        print(as_postgres_sql_query_str(stmt))
        print()

    _check(
        _list_filter_with_partial_file_id_stmt,
        user_or_project_filter=UserOrProjectFilter(
            user_id=None, project_ids=[uuid4() for _ in range(2)]
        ),
        file_id_prefix=None,
        partial_file_id=None,
        sha256_checksum=None,
        is_directory=False,
    )
    # WHERE file_meta_data.is_directory IS false ORDER BY file_meta_data.created_at ASC

    _check(
        _list_filter_with_partial_file_id_stmt,
        user_or_project_filter=UserOrProjectFilter(user_id=42, project_ids=[]),
        file_id_prefix=None,
        partial_file_id=None,
        sha256_checksum=None,
        is_directory=False,
    )
    # WHERE file_meta_data.user_id = '42' AND file_meta_data.is_directory IS false ORDER BY file_meta_data.created_at ASC

    _check(
        _list_filter_with_partial_file_id_stmt,
        user_or_project_filter=UserOrProjectFilter(
            user_id=42, project_ids=[uuid4() for _ in range(2)]
        ),
        file_id_prefix=None,
        partial_file_id=None,
        sha256_checksum=None,
        is_directory=False,
    )
    # WHERE (file_meta_data.user_id = '42' OR file_meta_data.project_id IN ('18d5'..., )) AND file_meta_data.is_directory IS false ORDER BY file_meta_data.created_at ASC

    _check(
        _list_filter_with_partial_file_id_stmt,
        user_or_project_filter=UserOrProjectFilter(
            user_id=42, project_ids=[uuid4() for _ in range(2)]
        ),
        file_id_prefix=None,
        partial_file_id=None,
        sha256_checksum=None,
        is_directory=False,
        limit=10,
        offset=1,
    )
    # (file_meta_data.user_id = '42' OR file_meta_data.project_id IN ('3cd9704db' ...)) AND file_meta_data.is_directory IS false ORDER BY file_meta_data.created_at ASC LIMIT 10 OFFSET 1

    # As used in SimcoreS3DataManager.list_files
    _check(
        _list_filter_with_partial_file_id_stmt,
        user_or_project_filter=UserOrProjectFilter(user_id=42, project_ids=[]),
        file_id_prefix=None,
        is_directory=None,
        partial_file_id="{project_id}/",
        sha256_checksum=None,
    )

    # As used in SimcoreS3DataManager.search_owned_files
    _check(
        _list_filter_with_partial_file_id_stmt,
        user_or_project_filter=UserOrProjectFilter(user_id=42, project_ids=[]),
        file_id_prefix="api/",
        partial_file_id=None,
        sha256_checksum=faker.sha256(),
        is_directory=False,
        limit=10,
        offset=0,
    )
