# pylint:disable=redefined-outer-name

from collections.abc import Awaitable, Callable

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from pydantic import NonNegativeInt
from simcore_postgres_database.models.folders import folders, folders_access_rights
from simcore_postgres_database.utils_folders import (
    FolderAlreadyExistsError,
    GroupIdDoesNotExistError,
    folders_create,
    folders_delete,
)


@pytest.fixture
async def create_user(
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
) -> Callable[[], Awaitable[RowProxy]]:
    async def _() -> RowProxy:
        return await create_fake_user(connection)

    return _


async def _assert_folder_entires(
    connection: SAConnection, *, count: NonNegativeInt
) -> None:
    async def _query_table(table_name: sa.Table) -> None:
        async with connection.execute(table_name.select()) as result:
            rows = await result.fetchall()
            assert rows is not None
            assert len(rows) == count

    await _query_table(folders)
    await _query_table(folders_access_rights)


async def test_folder_repository_create_base_usage(
    connection: SAConnection,
    create_user: Callable[[], Awaitable[RowProxy]],
):

    user: RowProxy = await create_user()
    user_gid = user.primary_gid

    # when GID is missing no entries should be present
    missing_gid = 10202023302
    await _assert_folder_entires(connection, count=0)
    with pytest.raises(GroupIdDoesNotExistError):
        await folders_create(connection, "f1", missing_gid)
    await _assert_folder_entires(connection, count=0)

    # create a folder ana subfolder of the same name
    f1_folder_id = await folders_create(connection, "f1", user_gid)
    await _assert_folder_entires(connection, count=1)
    await folders_create(connection, "f1", user_gid, parent=f1_folder_id)
    await _assert_folder_entires(connection, count=2)

    # inserting already existing folder fails
    with pytest.raises(FolderAlreadyExistsError):
        await folders_create(connection, "f1", user_gid)
    await _assert_folder_entires(connection, count=2)


async def test_folders_repository_delete_base_usage(
    connection: SAConnection, create_user: Callable[[], Awaitable[RowProxy]]
):
    user: RowProxy = await create_user()
    user_gid = user.primary_gid

    await _assert_folder_entires(connection, count=0)
    f1_folder_id = await folders_create(connection, "f1", user_gid)
    await _assert_folder_entires(connection, count=1)

    await folders_delete(connection, f1_folder_id, {user_gid})
    await _assert_folder_entires(connection, count=0)

    # TODO: add tests for the two exceptions
    # TODO: add test for subfolder deletion (maybe a more complex one with files in it?)
