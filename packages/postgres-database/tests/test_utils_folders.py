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
    CannotAlterOwnerPermissionsError,
    CannotGrantPermissionError,
    CouldNotFindFolderError,
    FolderAlreadyExistsError,
    GroupIdDoesNotExistError,
    InvalidFolderNameError,
    RequiresOwnerToMakeAdminError,
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
    admin: bool,
) -> None:
    async with connection.execute(
        folders_access_rights.select()
        .where(folders_access_rights.c.folder_id == folder_id)
        .where(folders_access_rights.c.gid == gid)
        .where(folders_access_rights.c.read == read)
        .where(folders_access_rights.c.write == write)
        .where(folders_access_rights.c.delete == delete)
        .where(folders_access_rights.c.admin == admin)
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


async def test_folder_share(
    connection: SAConnection, setup_users_and_groups: set[NonNegativeInt]
):
    owner_gid = _get_random_gid(setup_users_and_groups)
    admin_gid = _get_random_gid(setup_users_and_groups, {owner_gid})
    user_gid = _get_random_gid(setup_users_and_groups, {owner_gid, admin_gid})
    not_shared_with = _get_random_gid(
        setup_users_and_groups, {owner_gid, admin_gid, user_gid}
    )
    reciving_permissions_gid = _get_random_gid(
        setup_users_and_groups, {owner_gid, admin_gid, user_gid, not_shared_with}
    )

    async def _clear_gid_permissions(gid: _GroupID) -> None:
        await folder_share(
            connection,
            folder_id,
            {owner_gid},
            recipient_gid=gid,
            recipient_read=False,
            recipient_write=False,
            recipient_delete=False,
            recipient_admin=False,
        )
        await _assert_access_rights(
            connection,
            folder_id,
            gid,
            read=False,
            write=False,
            delete=False,
            admin=False,
        )

    folder_id = await folder_create(connection, "f1", owner_gid)

    # 1. make admin with all permissions
    await folder_share(
        connection,
        folder_id,
        {owner_gid},
        recipient_gid=admin_gid,
        # NOTE regardless of permissions granted, admin will always get all of them
        recipient_read=False,
        recipient_write=False,
        recipient_delete=False,
        recipient_admin=True,
    )
    await _assert_access_rights(
        connection, folder_id, admin_gid, read=True, write=True, delete=True, admin=True
    )

    # 2. make user with all permissions
    await folder_share(
        connection,
        folder_id,
        {owner_gid},
        recipient_gid=user_gid,
        recipient_read=True,
        recipient_write=True,
        recipient_delete=True,
        recipient_admin=False,
    )
    await _assert_access_rights(
        connection, folder_id, user_gid, read=True, write=True, delete=True, admin=False
    )

    # 3. no one is allowed to alter admin access rights
    for gid in (owner_gid, admin_gid, user_gid, not_shared_with):
        with pytest.raises(CannotAlterOwnerPermissionsError):
            await folder_share(
                connection,
                folder_id,
                {gid},
                recipient_gid=owner_gid,
                recipient_read=True,
                recipient_write=True,
                recipient_delete=True,
                recipient_admin=True,
            )

    # 4. only the owner can make an admin
    await _clear_gid_permissions(reciving_permissions_gid)
    for gid in (admin_gid, user_gid, not_shared_with):
        with pytest.raises(RequiresOwnerToMakeAdminError):
            await folder_share(
                connection,
                folder_id,
                {gid},
                recipient_gid=reciving_permissions_gid,
                recipient_read=True,
                recipient_write=True,
                recipient_delete=True,
                recipient_admin=True,
            )
        await _assert_access_rights(
            connection,
            folder_id,
            reciving_permissions_gid,
            read=False,
            write=False,
            delete=False,
            admin=False,
        )

    # 5. owner & admin can grant and remove: read, write and delete
    for gid in (owner_gid, admin_gid):
        # grant read, write and delete
        await folder_share(
            connection,
            folder_id,
            {gid},
            recipient_gid=reciving_permissions_gid,
            recipient_read=True,
            recipient_write=True,
            recipient_delete=True,
            recipient_admin=False,
        )
        await _assert_access_rights(
            connection,
            folder_id,
            reciving_permissions_gid,
            read=True,
            write=True,
            delete=True,
            admin=False,
        )
        # remove read, write and delete
        await folder_share(
            connection,
            folder_id,
            {gid},
            recipient_gid=reciving_permissions_gid,
            recipient_read=False,
            recipient_write=False,
            recipient_delete=False,
            recipient_admin=False,
        )
        await _assert_access_rights(
            connection,
            folder_id,
            reciving_permissions_gid,
            read=False,
            write=False,
            delete=False,
            admin=False,
        )

    # 6. other users cannot alter any permission combination
    for gid in (user_gid, not_shared_with):
        # grant read, write and delete
        for read, write, delete in itertools.product([True, False], repeat=3):
            with pytest.raises(CannotGrantPermissionError):
                await folder_share(
                    connection,
                    folder_id,
                    {gid},
                    recipient_gid=reciving_permissions_gid,
                    recipient_read=read,
                    recipient_write=write,
                    recipient_delete=delete,
                    recipient_admin=False,
                )


async def test_folder_delete_base_usage(
    connection: SAConnection, setup_users_and_groups: set[NonNegativeInt]
):
    owner_gid = _get_random_gid(setup_users_and_groups)

    missing_folder_id = 12313213
    with pytest.raises(CouldNotFindFolderError):
        await folder_delete(connection, missing_folder_id, {owner_gid})

    await _assert_folder_entires(connection, folder_count=0)
    f1_folder_id = await folder_create(connection, "f1", owner_gid)
    await _assert_folder_entires(connection, folder_count=1)

    await folder_delete(connection, f1_folder_id, {owner_gid})
    await _assert_folder_entires(connection, folder_count=0)

    # shared as user can user remove it's own folder entry?
    # this is based on access rights?

    # TODO: test for CouldNotDeleteMissingAccessError

    # TODO: delete root of a subfolder removes all elements inside

    # TODO: try deleting a folder with some projects inside it
