# pylint:disable=redefined-outer-name

import itertools
import secrets
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
    ParentIsNotWritableError,
    SharingMissingPermissionsError,
    _FolderID,
    _GroupID,
    folder_create,
    folder_delete,
    folder_share,
)


async def _assert_folder_entires(
    connection: SAConnection,
    *,
    folder_count: NonNegativeInt,
    access_rights_count: NonNegativeInt | None = None,
) -> None:
    async def _query_table(table_name: sa.Table, count: NonNegativeInt) -> None:
        async with connection.execute(table_name.select()) as result:
            rows = await result.fetchall()
            assert rows is not None
            assert len(rows) == count

    await _query_table(folders, folder_count)
    await _query_table(folders_access_rights, access_rights_count or folder_count)


async def _assert_access_rights(
    connection: SAConnection,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    read: bool,
    write: bool,
    delete: bool,
) -> None:
    async with connection.execute(
        folders_access_rights.select()
        .where(folders_access_rights.c.folder_id == folder_id)
        .where(folders_access_rights.c.gid == gid)
        .where(folders_access_rights.c.read == read)
        .where(folders_access_rights.c.write == write)
        .where(folders_access_rights.c.delete == delete)
    ) as result:
        rows = await result.fetchall()
        assert rows is not None
        assert len(rows) == 1


async def _create_folder_structure(
    connection: SAConnection,
    gid: NonNegativeInt,
    *,
    tree_depth: NonNegativeInt,
    subfolder_count: NonNegativeInt,
) -> tuple[NonNegativeInt, NonNegativeInt]:
    root_folder_id = await folder_create(connection, "root", gid)

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


async def _set_permissions(
    connection: SAConnection,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    read: bool,
    write: bool,
    delete: bool,
) -> None:
    await connection.execute(
        folders_access_rights.update()
        .where(folders_access_rights.c.folder_id == folder_id)
        .where(folders_access_rights.c.gid == gid)
        .values(read=read, write=write, delete=delete)
    )
    await _assert_access_rights(
        connection, folder_id, gid, read=read, write=write, delete=delete
    )


def _get_random_gid(
    all_gids: set[NonNegativeInt], already_picked: set[NonNegativeInt] | None = None
) -> NonNegativeInt:
    if already_picked is None:
        already_picked = set()
    to_random_pick = all_gids - already_picked
    return secrets.choice(list(to_random_pick))


@pytest.fixture
async def setup_users_and_groups(
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
) -> set[NonNegativeInt]:
    gids = set()
    for _ in range(10):
        user: RowProxy = await create_fake_user(connection)
        user_gid = user.primary_gid
        gids.add(user_gid)
    return gids


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
    connection: SAConnection, setup_users_and_groups: set[NonNegativeInt]
):
    user_gid = _get_random_gid(setup_users_and_groups)

    # when GID is missing no entries should be present
    missing_gid = 10202023302
    await _assert_folder_entires(connection, folder_count=0)
    with pytest.raises(GroupIdDoesNotExistError):
        await folder_create(connection, "f1", missing_gid)
    await _assert_folder_entires(connection, folder_count=0)

    # create a folder ana subfolder of the same name
    f1_folder_id = await folder_create(connection, "f1", user_gid)
    await _assert_folder_entires(connection, folder_count=1)
    await folder_create(connection, "f1", user_gid, parent=f1_folder_id)
    await _assert_folder_entires(connection, folder_count=2)

    # inserting already existing folder fails
    with pytest.raises(FolderAlreadyExistsError):
        await folder_create(connection, "f1", user_gid)
    await _assert_folder_entires(connection, folder_count=2)


async def _assert_shared_permissions(
    connection: SAConnection,
    folder_id: _FolderID,
    owner_user_gid: _GroupID,
    shared_with_user_gid: _GroupID,
    *,
    read: bool,
    write: bool,
    delete: bool,
) -> None:
    await folder_share(
        connection,
        folder_id,
        {owner_user_gid},
        recipient_group_id=shared_with_user_gid,
        recipient_read=read,
        recipient_write=write,
        recipient_delete=delete,
    )
    await _assert_folder_entires(connection, folder_count=1, access_rights_count=2)
    await _assert_access_rights(
        connection,
        folder_id,
        shared_with_user_gid,
        read=read,
        write=write,
        delete=delete,
    )


async def test_folder_share_basic(
    connection: SAConnection, setup_users_and_groups: set[NonNegativeInt]
):
    user_gid = _get_random_gid(setup_users_and_groups)
    another_user_gid = _get_random_gid(setup_users_and_groups, {user_gid})

    # create parent folder
    await _assert_folder_entires(connection, folder_count=0)
    folder_id = await folder_create(connection, "f1", user_gid)
    await _assert_folder_entires(connection, folder_count=1)

    for read, write, delete in itertools.combinations_with_replacement(
        (True, False), 3
    ):
        await _assert_shared_permissions(
            connection,
            folder_id,
            user_gid,
            another_user_gid,
            read=read,
            write=write,
            delete=delete,
        )


async def test_folder_share_no_permissions_raises_error(
    connection: SAConnection, setup_users_and_groups: set[NonNegativeInt]
):
    user_gid = _get_random_gid(setup_users_and_groups)
    another_user_gid = _get_random_gid(setup_users_and_groups, {user_gid})

    # create parent folder
    await _assert_folder_entires(connection, folder_count=0)
    folder_id = await folder_create(connection, "f1", user_gid)

    await _set_permissions(
        connection, folder_id, user_gid, read=False, write=False, delete=False
    )

    for read, write, delete in itertools.combinations_with_replacement(
        (True, False), 3
    ):
        with pytest.raises(SharingMissingPermissionsError):
            await _assert_shared_permissions(
                connection,
                folder_id,
                user_gid,
                another_user_gid,
                read=read,
                write=write,
                delete=delete,
            )

    # TODO: test error when sharing without permissions. Like removing own's permission to delete and sharing it with others


async def test_folder_share(
    connection: SAConnection, setup_users_and_groups: set[NonNegativeInt]
):
    # TODO: rewrite how we want this test to go:
    # 1 it's too verbose
    # 2 something is wrong, write the test as expected then figure it out

    user_gid = _get_random_gid(setup_users_and_groups)
    another_user_gid = _get_random_gid(setup_users_and_groups, {user_gid})

    # create parent folder
    await _assert_folder_entires(connection, folder_count=0)
    parent_folder_id = await folder_create(connection, "f1", user_gid)
    await _assert_folder_entires(connection, folder_count=1)

    # cannot create subfolder in parent if user differs
    with pytest.raises(ParentIsNotWritableError):
        await folder_create(connection, "f1", another_user_gid, parent=parent_folder_id)
    await _assert_folder_entires(connection, folder_count=1)

    # give permissions to parent (write)
    await folder_share(
        connection,
        parent_folder_id,
        {user_gid},
        recipient_group_id=another_user_gid,
        recipient_read=True,
        recipient_write=True,
        recipient_delete=False,
    )
    await _assert_access_rights(
        connection,
        parent_folder_id,
        another_user_gid,
        read=True,
        write=True,
        delete=False,
    )
    await _assert_folder_entires(connection, folder_count=1, access_rights_count=2)
    # add subfolder
    subfolder_id = await folder_create(
        connection, "f1", user_gid, parent=parent_folder_id
    )
    await _assert_folder_entires(connection, folder_count=2, access_rights_count=3)
    # delete subfolder (fails)
    with pytest.raises(CouldNotFindFolderError):
        await folder_delete(connection, subfolder_id, {another_user_gid})
    await _assert_folder_entires(connection, folder_count=2, access_rights_count=3)

    # give permissions to parent (delete)
    await folder_share(
        connection,
        parent_folder_id,
        {user_gid},
        recipient_group_id=another_user_gid,
        recipient_read=True,
        recipient_write=True,
        recipient_delete=True,
    )
    await _assert_access_rights(
        connection,
        parent_folder_id,
        another_user_gid,
        read=True,
        write=True,
        delete=True,
    )
    await _assert_folder_entires(connection, folder_count=2, access_rights_count=3)
    # delete subfolder
    await folder_delete(connection, subfolder_id, {another_user_gid})
    await _assert_folder_entires(connection, folder_count=1)

    # add subfolder again
    subfolder_id = await folder_create(
        connection, "f1", another_user_gid, parent=parent_folder_id
    )
    await _assert_folder_entires(connection, folder_count=2)
    # remove permissions
    await folder_share(
        connection,
        subfolder_id,
        {user_gid},
        recipient_group_id=another_user_gid,
        recipient_read=True,
        recipient_write=True,
        recipient_delete=False,
    )
    await _assert_folder_entires(connection, folder_count=2)
    # delete subfolder (raises error)
    await folder_delete(connection, subfolder_id, {user_gid})
    await _assert_folder_entires(connection, folder_count=2)

    # TODO: also add the listing of folder contents
    # this also must withstand the same rules


async def test_folder_delete_base_usage(
    connection: SAConnection, setup_users_and_groups: set[NonNegativeInt]
):
    user_gid = _get_random_gid(setup_users_and_groups)

    missing_folder_id = 12313213
    with pytest.raises(CouldNotFindFolderError):
        await folder_delete(connection, missing_folder_id, {user_gid})

    await _assert_folder_entires(connection, folder_count=0)
    f1_folder_id = await folder_create(connection, "f1", user_gid)
    await _assert_folder_entires(connection, folder_count=1)

    with pytest.raises(CouldNotDeleteMissingAccessError):
        await folder_delete(connection, f1_folder_id, {user_gid})

    await folder_update_access(connection, f1_folder_id, user_gid, new_delete=True)
    await folder_delete(connection, f1_folder_id, {user_gid})
    await _assert_folder_entires(connection, folder_count=0)

    # delete root of a subfolder removes all elements inside
    root_folder_id, total_created_items = await _create_folder_structure(
        connection, user_gid, tree_depth=3, subfolder_count=4
    )
    # NOTE: only the root node is give delete access
    await folder_update_access(connection, root_folder_id, user_gid, new_delete=True)
    await _assert_folder_entires(connection, folder_count=total_created_items)
    await folder_delete(connection, root_folder_id, {user_gid})
    await _assert_folder_entires(connection, folder_count=0)

    # TODO: try removal with existing gid but no access
