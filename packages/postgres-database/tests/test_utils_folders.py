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
from simcore_postgres_database.models.folders import (
    folders,
    folders_access_rights,
    folders_to_projects,
)
from simcore_postgres_database.utils_folders import (
    _FOLDER_NAME_MAX_LENGTH,
    _FOLDER_NAMES_RESERVED_WINDOWS,
    CannotAlterOwnerPermissionsError,
    CannotGrantPermissionError,
    CannotRenameFolderError,
    CouldNotDeleteMissingAccessError,
    CouldNotFindFolderError,
    FolderAlreadyExistsError,
    GroupIdDoesNotExistError,
    InvalidFolderNameError,
    NoAccessToFolderFoundrError,
    ProjectAlreadyExistsInFolderError,
    RequiresOwnerToMakeAdminError,
    _FolderID,
    _GroupID,
    _ProjectID,
    folder_add_project,
    folder_create,
    folder_delete,
    folder_rename,
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


async def _assert_folder_name(
    connection: SAConnection, folder_id: _FolderID, *, expected_name: str
) -> None:
    async with connection.execute(
        folders.select().where(folders.c.id == folder_id)
    ) as result:
        rows = await result.fetchall()
        assert rows is not None
        assert len(rows) == 1
        rown = rows[0]
        assert rown.name == expected_name


async def _assert_project_in_folder(
    connection: SAConnection,
    *,
    folder_id: _FolderID,
    project_id: _ProjectID,
    owner: _GroupID,
):
    async with connection.execute(
        folders_to_projects.select()
        .where(folders_to_projects.c.folder_id == folder_id)
        .where(folders_to_projects.c.project_id == project_id)
        .where(folders_to_projects.c.owner == owner)
    ) as result:
        rows = await result.fetchall()
        assert rows is not None
        assert len(rows) == 1


def _get_random_gid(
    all_gids: set[_GroupID], already_picked: set[_GroupID] | None = None
) -> _GroupID:
    if already_picked is None:
        already_picked = set()
    to_random_pick = all_gids - already_picked
    return secrets.choice(list(to_random_pick))


def _get_random_project_id(
    all_gids: set[_ProjectID], already_picked: set[_ProjectID] | None = None
) -> _ProjectID:
    if already_picked is None:
        already_picked = set()
    to_random_pick = all_gids - already_picked
    return secrets.choice(list(to_random_pick))


@pytest.fixture
async def setup_users(
    connection: SAConnection, create_fake_user: Callable[..., Awaitable[RowProxy]]
) -> list[RowProxy]:
    users: list[RowProxy] = []
    for _ in range(10):
        users.append(await create_fake_user(connection))  # noqa: PERF401
    return users


@pytest.fixture
async def setup_users_and_groups(setup_users: list[RowProxy]) -> set[_GroupID]:
    return {u.primary_gid for u in setup_users}


@pytest.fixture
async def setup_projects_for_users(
    connection: SAConnection,
    setup_users: list[RowProxy],
    create_fake_project: Callable[..., Awaitable[RowProxy]],
) -> set[_ProjectID]:
    projects: set[_ProjectID] = set()
    for user in setup_users:
        project = await create_fake_project(connection, user)
        projects.add(project.id)
    return projects


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
    connection: SAConnection, setup_users_and_groups: set[_GroupID]
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


async def test_folder_rename(
    connection: SAConnection, setup_users_and_groups: set[_GroupID]
):
    owner_gid = _get_random_gid(setup_users_and_groups)
    admin_gid = _get_random_gid(setup_users_and_groups, {owner_gid})
    user_gid = _get_random_gid(setup_users_and_groups, {owner_gid, admin_gid})
    not_shared_with_gid = _get_random_gid(
        setup_users_and_groups, {owner_gid, admin_gid, user_gid}
    )

    folder_id = await folder_create(connection, "f1", owner_gid)
    await _assert_folder_entires(connection, folder_count=1)

    # 1. rename as owner
    await folder_rename(connection, folder_id, gids={owner_gid}, name="owner_f1")
    await _assert_folder_entires(connection, folder_count=1)
    await _assert_folder_name(connection, folder_id, expected_name="owner_f1")

    # 2. renaming as admin user
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
    await folder_rename(connection, folder_id, gids={admin_gid}, name="admin_f1")
    await _assert_folder_name(connection, folder_id, expected_name="admin_f1")

    # 3. try to rename as a regular user raises error
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
    with pytest.raises(CannotRenameFolderError):
        await folder_rename(connection, folder_id, gids={user_gid}, name="user_f1")

    # 4. try to rename as a user with no access raises error
    with pytest.raises(CannotRenameFolderError):
        await folder_rename(
            connection, folder_id, gids={not_shared_with_gid}, name="not_shared_with_f1"
        )


async def test_folder_share(
    connection: SAConnection, setup_users_and_groups: set[_GroupID]
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

    # 0. share not existing folder
    missing_folder_id = 2137912783
    with pytest.raises(CannotGrantPermissionError):
        await folder_share(
            connection,
            missing_folder_id,
            {owner_gid},
            recipient_gid=admin_gid,
            recipient_read=False,
            recipient_write=False,
            recipient_delete=False,
            recipient_admin=False,
        )

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
    connection: SAConnection, setup_users_and_groups: set[_GroupID]
):
    owner_gid = _get_random_gid(setup_users_and_groups)
    user_gid = _get_random_gid(setup_users_and_groups, {owner_gid, owner_gid})

    # 1 raise error if folder is not found
    missing_folder_id = 12313213
    with pytest.raises(CouldNotFindFolderError):
        await folder_delete(connection, missing_folder_id, owner_gid)

    # 2 removes owner's folder
    await _assert_folder_entires(connection, folder_count=0)
    f1_folder_id = await folder_create(connection, "f1", owner_gid)
    await _assert_folder_entires(connection, folder_count=1)
    await _assert_access_rights(
        connection,
        f1_folder_id,
        owner_gid,
        read=True,
        write=True,
        delete=True,
        admin=True,
    )
    await folder_delete(connection, f1_folder_id, owner_gid)
    await _assert_folder_entires(connection, folder_count=0)

    # 3 create folder and share it with a user -> remove via user -> only the user's fodler entry is removed
    f1_folder_id = await folder_create(connection, "f1", owner_gid)
    await _assert_folder_entires(connection, folder_count=1)
    # 3.1 share with no delete permissions -> does not delete
    await folder_share(
        connection,
        f1_folder_id,
        sharing_gids={owner_gid},
        recipient_gid=user_gid,
        recipient_read=False,
        recipient_write=False,
        recipient_delete=False,
        recipient_admin=False,
    )
    await _assert_folder_entires(connection, folder_count=1, access_rights_count=2)
    await _assert_access_rights(
        connection,
        f1_folder_id,
        owner_gid,
        read=True,
        write=True,
        delete=True,
        admin=True,
    )
    await _assert_access_rights(
        connection,
        f1_folder_id,
        user_gid,
        read=False,
        write=False,
        delete=False,
        admin=False,
    )

    with pytest.raises(CouldNotDeleteMissingAccessError):
        await folder_delete(connection, f1_folder_id, user_gid)

    # 3.2 share with delete permissions -> will delete
    # -> removes folder shared with user and original remains
    await folder_share(
        connection,
        f1_folder_id,
        sharing_gids={owner_gid},
        recipient_gid=user_gid,
        recipient_read=False,
        recipient_write=False,
        recipient_delete=True,
        recipient_admin=False,
    )
    await _assert_folder_entires(connection, folder_count=1, access_rights_count=2)
    await _assert_access_rights(
        connection,
        f1_folder_id,
        owner_gid,
        read=True,
        write=True,
        delete=True,
        admin=True,
    )
    await _assert_access_rights(
        connection,
        f1_folder_id,
        user_gid,
        read=False,
        write=False,
        delete=True,
        admin=False,
    )

    # only removes the access_rights entry and not the owner's one
    await folder_delete(connection, f1_folder_id, user_gid)
    await _assert_folder_entires(connection, folder_count=1)
    await _assert_access_rights(
        connection,
        f1_folder_id,
        owner_gid,
        read=True,
        write=True,
        delete=True,
        admin=True,
    )

    # 4 share folder it with a user -> remove via owner -> both entries are removed
    await _assert_folder_entires(connection, folder_count=1)
    # share with minimum permissions
    await folder_share(
        connection,
        f1_folder_id,
        sharing_gids={owner_gid},
        recipient_gid=user_gid,
        recipient_read=False,
        recipient_write=False,
        recipient_delete=True,
        recipient_admin=False,
    )
    await _assert_access_rights(
        connection,
        f1_folder_id,
        owner_gid,
        read=True,
        write=True,
        delete=True,
        admin=True,
    )
    await _assert_access_rights(
        connection,
        f1_folder_id,
        user_gid,
        read=False,
        write=False,
        delete=True,
        admin=False,
    )
    await _assert_folder_entires(connection, folder_count=1, access_rights_count=2)

    await folder_delete(connection, f1_folder_id, owner_gid)
    await _assert_folder_entires(connection, folder_count=0)

    # 5 create a folder with subfolders x levels deep -> delete it removes all elements
    f1_folder_id = await folder_create(connection, "f1", owner_gid)
    f2_folder_id = await folder_create(connection, "f2", owner_gid, parent=f1_folder_id)
    f3_folder_id = await folder_create(connection, "f3", owner_gid, parent=f2_folder_id)
    await folder_create(connection, "f4", owner_gid, parent=f3_folder_id)
    await _assert_folder_entires(connection, folder_count=4)
    await folder_delete(connection, f1_folder_id, owner_gid)
    await _assert_folder_entires(connection, folder_count=0)

    # 6 create a folder-> share it-> user creates subfolders x levels deep -> removes only owner directories
    f1_folder_id = await folder_create(connection, "f1", owner_gid)
    await folder_create(connection, "f2_owner", owner_gid, parent=f1_folder_id)
    await folder_share(
        connection,
        f1_folder_id,
        {owner_gid},
        recipient_gid=user_gid,
        recipient_read=True,
        recipient_write=True,
        recipient_delete=True,
        recipient_admin=False,
    )

    f2_folder_id = await folder_create(connection, "f2", user_gid, parent=f1_folder_id)
    f3_folder_id = await folder_create(connection, "f3", user_gid, parent=f2_folder_id)
    f4_folder_id = await folder_create(connection, "f4", user_gid, parent=f3_folder_id)
    await _assert_folder_entires(connection, folder_count=5, access_rights_count=6)
    await folder_delete(connection, f1_folder_id, owner_gid)
    await _assert_folder_entires(connection, folder_count=3)
    for folder_id in (f2_folder_id, f3_folder_id, f4_folder_id):
        await _assert_access_rights(
            connection,
            folder_id,
            user_gid,
            read=True,
            write=True,
            delete=True,
            admin=True,
        )

    # TODO: try deleting a folder with some projects inside it


async def test_folder_add_project(
    connection: SAConnection,
    setup_users_and_groups: set[_GroupID],
    setup_projects_for_users: set[_ProjectID],
):
    owner_gid = _get_random_gid(setup_users_and_groups)
    another_user_gid = _get_random_gid(setup_users_and_groups, {owner_gid})
    user_with_access_gid = _get_random_gid(
        setup_users_and_groups, {owner_gid, another_user_gid}
    )

    folder_id = await folder_create(connection, "f1", owner_gid)

    await folder_share(
        connection,
        folder_id,
        sharing_gids={owner_gid},
        recipient_gid=user_with_access_gid,
        recipient_write=True,
    )

    project_id = _get_random_project_id(setup_projects_for_users)

    await folder_add_project(connection, folder_id, owner_gid, project_id=project_id)
    await _assert_project_in_folder(
        connection, folder_id=folder_id, project_id=project_id, owner=owner_gid
    )

    with pytest.raises(NoAccessToFolderFoundrError):
        await folder_add_project(
            connection, folder_id, another_user_gid, project_id=project_id
        )

    with pytest.raises(ProjectAlreadyExistsInFolderError) as exc:
        await folder_add_project(
            connection, folder_id, owner_gid, project_id=project_id
        )
    assert f"gid={owner_gid}" in f"{exc.value}"
    assert f"owner={owner_gid}" in f"{exc.value}"

    with pytest.raises(ProjectAlreadyExistsInFolderError) as exc:
        await folder_add_project(
            connection, folder_id, user_with_access_gid, project_id=project_id
        )

    assert f"gid={user_with_access_gid}" in f"{exc.value}"
    assert f"owner={owner_gid}" in f"{exc.value}"
