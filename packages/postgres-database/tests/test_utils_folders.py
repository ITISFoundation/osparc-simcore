# pylint:disable=redefined-outer-name

from collections.abc import Awaitable, Callable
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from pydantic import NonNegativeInt
from simcore_postgres_database.models.folders import folders, folders_access_rights
from simcore_postgres_database.utils_folders import (
    _FOLDER_NAME_MAX_LENGTH,
    _FOLDER_NAMES_RESERVED_WINDOWS,
    CouldNotDeleteMissingAccessError,
    CouldNotFindFolderError,
    FolderAlreadyExistsError,
    GroupIdDoesNotExistError,
    InvalidFolderNameError,
    folder_create,
    folder_delete,
    folder_update_access,
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


async def _create_folder_structure(
    connection: SAConnection,
    gid: NonNegativeInt,
    *,
    tree_depth: NonNegativeInt,
    subfolder_count: NonNegativeInt,
) -> tuple[NonNegativeInt, NonNegativeInt]:
    root_folder_id = await folder_create(connection, "root", gid, write=True)

    async def _create_sub_folders(
        parent_folder_id: NonNegativeInt,
        current_level: NonNegativeInt,
        max_levels: NonNegativeInt,
        subfolder_count: NonNegativeInt,
    ) -> NonNegativeInt:
        if current_level > max_levels:
            return 0

        creation_count = 0
        for i in range(subfolder_count):
            folder_id = await folder_create(
                connection,
                f"{current_level}_{i}",
                gid,
                parent=parent_folder_id,
                write=True,
            )
            creation_count += 1
            creation_count += await _create_sub_folders(
                folder_id, current_level + 1, max_levels, subfolder_count
            )

        return creation_count

    subfolder_count = await _create_sub_folders(
        root_folder_id, 1, tree_depth, subfolder_count
    )
    return root_folder_id, subfolder_count + 1


# TODO: fixture that creates 10 users and each of them has
# own_group and all other group to which they do not have access to initially
# use all these to run tests against whatever endpoint we write
# we can create a various mix of things


@pytest.mark.parametrize(
    "invalid_name",
    [
        None,
        "",
        "/",
        ":",
        '"',
        "<",
        ">",
        "\\",
        "|",
        "?",
        "My/Folder",
        "MyFolder<",
        "CON",
        "AUX",
        "My*Folder",
        "A" * (_FOLDER_NAME_MAX_LENGTH + 1),
        *_FOLDER_NAMES_RESERVED_WINDOWS,
    ],
)
async def test_folder_create_wrong_folder_name(invalid_name: str):
    with pytest.raises(InvalidFolderNameError):
        await folder_create(Mock(), invalid_name, Mock())


async def test_folder_create_base_usage(
    connection: SAConnection,
    create_user: Callable[[], Awaitable[RowProxy]],
):

    user: RowProxy = await create_user()
    user_gid = user.primary_gid

    # when GID is missing no entries should be present
    missing_gid = 10202023302
    await _assert_folder_entires(connection, count=0)
    with pytest.raises(GroupIdDoesNotExistError):
        await folder_create(connection, "f1", missing_gid)
    await _assert_folder_entires(connection, count=0)

    # create a folder ana subfolder of the same name
    f1_folder_id = await folder_create(connection, "f1", user_gid, write=True)
    await _assert_folder_entires(connection, count=1)
    await folder_create(connection, "f1", user_gid, parent=f1_folder_id)
    await _assert_folder_entires(connection, count=2)

    # inserting already existing folder fails
    with pytest.raises(FolderAlreadyExistsError):
        await folder_create(connection, "f1", user_gid)
    await _assert_folder_entires(connection, count=2)


async def test_folder_delete_base_usage(
    connection: SAConnection, create_user: Callable[[], Awaitable[RowProxy]]
):
    user: RowProxy = await create_user()
    user_gid = user.primary_gid

    missing_folder_id = 12313213
    with pytest.raises(CouldNotFindFolderError):
        await folder_delete(connection, missing_folder_id, {user_gid})

    await _assert_folder_entires(connection, count=0)
    f1_folder_id = await folder_create(connection, "f1", user_gid)
    await _assert_folder_entires(connection, count=1)

    with pytest.raises(CouldNotDeleteMissingAccessError):
        await folder_delete(connection, f1_folder_id, {user_gid})

    await folder_update_access(connection, f1_folder_id, user_gid, new_delete=True)
    await folder_delete(connection, f1_folder_id, {user_gid})
    await _assert_folder_entires(connection, count=0)

    # delete root of a subfolder removes all elements inside
    root_folder_id, total_created_items = await _create_folder_structure(
        connection, user_gid, tree_depth=3, subfolder_count=4
    )
    # NOTE: only the root node is give delete access
    await folder_update_access(connection, root_folder_id, user_gid, new_delete=True)
    await _assert_folder_entires(connection, count=total_created_items)
    await folder_delete(connection, root_folder_id, {user_gid})
    await _assert_folder_entires(connection, count=0)
