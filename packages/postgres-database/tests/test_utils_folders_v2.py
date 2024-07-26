# pylint:disable=redefined-outer-name
# pylint:disable=unused-variable

import secrets
from collections.abc import Awaitable, Callable
from typing import NamedTuple
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
from simcore_postgres_database.models.groups import GroupType, groups
from simcore_postgres_database.utils_folders_v2 import (
    _FOLDER_NAME_MAX_LENGTH,
    _FOLDER_NAMES_RESERVED_WINDOWS,
    _ROLE_TO_PERMISSIONS,
    EDITOR_PERMISSIONS,
    NO_ACCESS_PERMISSIONS,
    OWNER_PERMISSIONS,
    VIEWER_PERMISSIONS,
    CannotMoveFolderSharedViaNonPrimaryGroupError,
    FolderAccessRole,
    FolderAlreadyExistsError,
    FolderEntry,
    FolderNotFoundError,
    FolderNotSharedWithGidError,
    GroupIdDoesNotExistError,
    InsufficientPermissionsError,
    InvalidFolderNameError,
    _FolderID,
    _FolderPermissions,
    _get_permissions_from_role,
    _get_top_most_access_rights_entry,
    _get_true_permissions,
    _GroupID,
    _ProjectID,
    _requires,
    folder_add_project,
    folder_create,
    folder_delete,
    folder_list,
    folder_move,
    folder_remove_project,
    folder_share_or_update_permissions,
    folder_update,
)
from sqlalchemy.sql.elements import ColumnElement


def test_permissions_integrity():
    assert set(FolderAccessRole) == set(_ROLE_TO_PERMISSIONS.keys())


@pytest.mark.parametrize(
    "role, expected_permissions",
    [
        (FolderAccessRole.VIEWER, {"read": True, "write": False, "delete": False}),
        (FolderAccessRole.EDITOR, {"read": True, "write": True, "delete": False}),
        (FolderAccessRole.OWNER, {"read": True, "write": True, "delete": True}),
    ],
)
def test_role_permissions(
    role: FolderAccessRole, expected_permissions: dict[str, bool]
):
    assert _get_permissions_from_role(role) == expected_permissions


@pytest.mark.parametrize(
    "permissions, expected",
    [
        ([], {"read": False, "write": False, "delete": False}),
        ([VIEWER_PERMISSIONS], {"read": True, "write": False, "delete": False}),
        ([EDITOR_PERMISSIONS], {"read": True, "write": True, "delete": False}),
        (
            [EDITOR_PERMISSIONS, VIEWER_PERMISSIONS],
            {"read": True, "write": True, "delete": False},
        ),
        ([OWNER_PERMISSIONS], {"read": True, "write": True, "delete": True}),
        (
            [OWNER_PERMISSIONS, EDITOR_PERMISSIONS],
            {"read": True, "write": True, "delete": True},
        ),
        (
            [OWNER_PERMISSIONS, EDITOR_PERMISSIONS, VIEWER_PERMISSIONS],
            {"read": True, "write": True, "delete": True},
        ),
    ],
)
def test__requires_permissions(
    permissions: list[_FolderPermissions] | None, expected: dict[str, bool]
):
    assert _requires(*permissions) == expected


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


def test__get_where_clause():
    assert isinstance(
        _get_true_permissions(VIEWER_PERMISSIONS, folders_access_rights), ColumnElement
    )
    assert isinstance(
        _get_true_permissions(EDITOR_PERMISSIONS, folders_access_rights), ColumnElement
    )
    assert isinstance(
        _get_true_permissions(OWNER_PERMISSIONS, folders_access_rights), ColumnElement
    )
    assert isinstance(
        _get_true_permissions(
            {"read": False, "write": False, "delete": False}, folders_access_rights
        ),
        bool,
    )


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


async def _assert_folder_entires(
    connection: SAConnection,
    *,
    folder_count: NonNegativeInt,
    access_rights_count: NonNegativeInt | None = None,
) -> None:
    async def _query_table(table_name: sa.Table, count: NonNegativeInt) -> None:
        result = await connection.execute(table_name.select())
        rows = await result.fetchall()
        assert rows is not None
        assert len(rows) == count

    await _query_table(folders, folder_count)
    await _query_table(folders_access_rights, access_rights_count or folder_count)


async def _assert_folder_permissions(
    connection: SAConnection,
    *,
    folder_id: _FolderID,
    gid: _GroupID,
    role: FolderAccessRole,
) -> None:
    result = await connection.execute(
        sa.select([folders_access_rights.c.folder_id])
        .where(folders_access_rights.c.folder_id == folder_id)
        .where(folders_access_rights.c.gid == gid)
        .where(
            _get_true_permissions(
                _get_permissions_from_role(role), folders_access_rights
            )
        )
    )
    rows = await result.fetchall()
    assert rows is not None
    assert len(rows) == 1


async def _assert_name_and_description(
    connection: SAConnection,
    folder_id: _FolderID,
    *,
    name: str,
    description: str,
):
    async with connection.execute(
        sa.select([folders.c.name, folders.c.description]).where(
            folders.c.id == folder_id
        )
    ) as result_proxy:
        results = await result_proxy.fetchall()
        assert results
        assert len(results) == 1
        result = results[0]
        assert result["name"] == name
        assert result["description"] == description


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


async def test_folder_create(
    connection: SAConnection, setup_users_and_groups: set[_GroupID]
):
    owner_gid = _get_random_gid(setup_users_and_groups)

    # when GID is missing no entries should be present
    missing_gid = 10202023302
    await _assert_folder_entires(connection, folder_count=0)
    with pytest.raises(GroupIdDoesNotExistError):
        await folder_create(connection, "f1", missing_gid)
    await _assert_folder_entires(connection, folder_count=0)

    # create a folder ana subfolder of the same name
    f1_folder_id = await folder_create(connection, "f1", owner_gid)
    await _assert_folder_entires(connection, folder_count=1)
    await folder_create(connection, "f1", owner_gid, parent=f1_folder_id)
    await _assert_folder_entires(connection, folder_count=2)

    # inserting already existing folder fails
    with pytest.raises(FolderAlreadyExistsError):
        await folder_create(connection, "f1", owner_gid)
    await _assert_folder_entires(connection, folder_count=2)


async def test__get_top_most_access_rights_entry(
    connection: SAConnection, setup_users_and_groups: set[_GroupID]
):
    owner_a_gid = _get_random_gid(setup_users_and_groups)
    owner_b_gid = _get_random_gid(setup_users_and_groups, already_picked={owner_a_gid})
    owner_c_gid = _get_random_gid(
        setup_users_and_groups, already_picked={owner_a_gid, owner_b_gid}
    )
    owner_d_gid = _get_random_gid(
        setup_users_and_groups, already_picked={owner_a_gid, owner_b_gid, owner_c_gid}
    )
    editor_a_gid = _get_random_gid(
        setup_users_and_groups,
        already_picked={owner_a_gid, owner_b_gid, owner_c_gid, owner_d_gid},
    )
    editor_b_gid = _get_random_gid(
        setup_users_and_groups,
        already_picked={
            owner_a_gid,
            owner_b_gid,
            owner_c_gid,
            owner_d_gid,
            editor_a_gid,
        },
    )

    # share folder with all owners
    root_folder_id = await folder_create(connection, "root_folder", owner_a_gid)
    for other_owner_gid in (owner_b_gid, owner_c_gid, owner_d_gid):
        await folder_share_or_update_permissions(
            connection,
            root_folder_id,
            sharing_gid=owner_a_gid,
            recipient_gid=other_owner_gid,
            recipient_role=FolderAccessRole.OWNER,
        )
    await folder_share_or_update_permissions(
        connection,
        root_folder_id,
        sharing_gid=owner_a_gid,
        recipient_gid=editor_a_gid,
        recipient_role=FolderAccessRole.EDITOR,
    )
    await _assert_folder_entires(connection, folder_count=1, access_rights_count=5)

    # create folders
    b_folder_id = await folder_create(
        connection, "b_folder", owner_b_gid, parent=root_folder_id
    )
    c_folder_id = await folder_create(
        connection, "c_folder", owner_c_gid, parent=root_folder_id
    )
    d_folder_id = await folder_create(
        connection, "d_folder", owner_d_gid, parent=c_folder_id
    )
    editor_a_folder_id = await folder_create(
        connection, "editor_a_folder", editor_a_gid, parent=d_folder_id
    )
    await _assert_folder_entires(connection, folder_count=5, access_rights_count=9)
    # share existing folder in hierarchy with a new user
    await folder_share_or_update_permissions(
        connection,
        d_folder_id,
        sharing_gid=owner_a_gid,
        recipient_gid=editor_b_gid,
        recipient_role=FolderAccessRole.EDITOR,
    )
    await _assert_folder_entires(connection, folder_count=5, access_rights_count=10)

    # FOLDER STRUCTURE {`fodler_name`(`owner_gid`)[`shared_with_gid`, ...]}
    #  `root_folder`(`owner_a`)[`owner_b`,`owner_c`,`owner_d`,`editor_a`]
    #   - `b_folder`(`owner_b`)
    #   - `c_folder`(`owner_c`):
    #       - `d_folder`(`owner_d`)[`editor_b`]:
    #           - `editor_a_folder`(`editor_a`)

    # check top most parent resolution
    async def _assert_reloves_to(
        *,
        target_folder_id: _FolderID,
        gid: _GroupID,
        permissions: _FolderPermissions,
        expected_folder_id: _FolderID,
        expected_gids: set[_FolderID],
    ) -> None:
        resolved_parent = await _get_top_most_access_rights_entry(
            connection,
            target_folder_id,
            gid,
            permissions=permissions,
            # NOTE: this is the more restricitve case
            # and we test against exact user roles,
            # the APIs use only a subset of the permissions ususally set to True
            enforece_all_permissions=True,
        )
        assert resolved_parent
        assert resolved_parent["folder_id"] == expected_folder_id
        assert resolved_parent["gid"] in expected_gids

    await _assert_reloves_to(
        target_folder_id=root_folder_id,
        gid=owner_a_gid,
        permissions=OWNER_PERMISSIONS,
        expected_folder_id=root_folder_id,
        expected_gids={owner_a_gid},
    )
    await _assert_reloves_to(
        target_folder_id=b_folder_id,
        gid=owner_b_gid,
        permissions=OWNER_PERMISSIONS,
        expected_folder_id=root_folder_id,
        expected_gids={owner_b_gid},
    )
    await _assert_reloves_to(
        target_folder_id=c_folder_id,
        gid=owner_c_gid,
        permissions=OWNER_PERMISSIONS,
        expected_folder_id=root_folder_id,
        expected_gids={owner_c_gid},
    )
    await _assert_reloves_to(
        target_folder_id=d_folder_id,
        gid=owner_d_gid,
        permissions=OWNER_PERMISSIONS,
        expected_folder_id=root_folder_id,
        expected_gids={owner_d_gid},
    )
    await _assert_reloves_to(
        target_folder_id=editor_a_folder_id,
        gid=editor_a_gid,
        permissions=EDITOR_PERMISSIONS,
        expected_folder_id=root_folder_id,
        expected_gids={editor_a_gid},
    )
    await _assert_reloves_to(
        target_folder_id=editor_a_folder_id,
        gid=editor_b_gid,
        permissions=EDITOR_PERMISSIONS,
        expected_folder_id=d_folder_id,
        expected_gids={editor_b_gid},
    )


async def test_folder_share_or_update_permissions(
    connection: SAConnection, setup_users_and_groups: set[_GroupID]
):
    owner_gid = _get_random_gid(setup_users_and_groups)
    other_owner_gid = _get_random_gid(
        setup_users_and_groups, already_picked={owner_gid}
    )
    editor_gid = _get_random_gid(
        setup_users_and_groups, already_picked={owner_gid, other_owner_gid}
    )
    viewer_gid = _get_random_gid(
        setup_users_and_groups, already_picked={owner_gid, other_owner_gid, editor_gid}
    )
    no_access_gid = _get_random_gid(
        setup_users_and_groups,
        already_picked={owner_gid, other_owner_gid, editor_gid, viewer_gid},
    )
    share_with_error_gid = _get_random_gid(
        setup_users_and_groups,
        already_picked={
            owner_gid,
            other_owner_gid,
            editor_gid,
            viewer_gid,
            no_access_gid,
        },
    )

    # 1. folder does not exist
    missing_folder_id = 12313123232
    with pytest.raises(FolderNotFoundError):
        await folder_share_or_update_permissions(
            connection,
            missing_folder_id,
            sharing_gid=owner_gid,
            recipient_gid=share_with_error_gid,
            recipient_role=FolderAccessRole.OWNER,
        )
    await _assert_folder_entires(connection, folder_count=0)

    # 2. share existing folder with all possible roles
    folder_id = await folder_create(connection, "f1", owner_gid)
    await _assert_folder_entires(connection, folder_count=1)
    await _assert_folder_permissions(
        connection, folder_id=folder_id, gid=owner_gid, role=FolderAccessRole.OWNER
    )

    await folder_share_or_update_permissions(
        connection,
        folder_id,
        sharing_gid=owner_gid,
        recipient_gid=other_owner_gid,
        recipient_role=FolderAccessRole.OWNER,
    )
    await _assert_folder_entires(connection, folder_count=1, access_rights_count=2)
    await _assert_folder_permissions(
        connection,
        folder_id=folder_id,
        gid=other_owner_gid,
        role=FolderAccessRole.OWNER,
    )

    await folder_share_or_update_permissions(
        connection,
        folder_id,
        sharing_gid=owner_gid,
        recipient_gid=editor_gid,
        recipient_role=FolderAccessRole.EDITOR,
    )
    await _assert_folder_entires(connection, folder_count=1, access_rights_count=3)
    await _assert_folder_permissions(
        connection, folder_id=folder_id, gid=editor_gid, role=FolderAccessRole.EDITOR
    )

    await folder_share_or_update_permissions(
        connection,
        folder_id,
        sharing_gid=owner_gid,
        recipient_gid=viewer_gid,
        recipient_role=FolderAccessRole.VIEWER,
    )
    await _assert_folder_entires(connection, folder_count=1, access_rights_count=4)
    await _assert_folder_permissions(
        connection, folder_id=folder_id, gid=viewer_gid, role=FolderAccessRole.VIEWER
    )

    await folder_share_or_update_permissions(
        connection,
        folder_id,
        sharing_gid=owner_gid,
        recipient_gid=no_access_gid,
        recipient_role=FolderAccessRole.NO_ACCESS,
    )
    await _assert_folder_entires(connection, folder_count=1, access_rights_count=5)
    await _assert_folder_permissions(
        connection,
        folder_id=folder_id,
        gid=no_access_gid,
        role=FolderAccessRole.NO_ACCESS,
    )

    # 3. roles without permissions cannot share with any role
    for recipient_role in FolderAccessRole:
        for no_access_gids in (editor_gid, viewer_gid, no_access_gid):
            with pytest.raises(InsufficientPermissionsError):
                await folder_share_or_update_permissions(
                    connection,
                    folder_id,
                    sharing_gid=no_access_gids,
                    recipient_gid=share_with_error_gid,
                    recipient_role=recipient_role,
                )
            await _assert_folder_entires(
                connection, folder_count=1, access_rights_count=5
            )

        with pytest.raises(FolderNotSharedWithGidError):
            await folder_share_or_update_permissions(
                connection,
                folder_id,
                sharing_gid=share_with_error_gid,
                recipient_gid=share_with_error_gid,
                recipient_role=recipient_role,
            )
        await _assert_folder_entires(connection, folder_count=1, access_rights_count=5)

    # 4. all users loose permission on the foler including the issuer
    # NOTE: anoteher_owner dropped owner's permission and his permission to no access!
    for gid_to_drop_permission in (owner_gid, editor_gid, viewer_gid, other_owner_gid):
        await folder_share_or_update_permissions(
            connection,
            folder_id,
            sharing_gid=other_owner_gid,
            recipient_gid=gid_to_drop_permission,
            recipient_role=FolderAccessRole.NO_ACCESS,
        )
        await _assert_folder_entires(connection, folder_count=1, access_rights_count=5)
        await _assert_folder_permissions(
            connection,
            folder_id=folder_id,
            gid=gid_to_drop_permission,
            role=FolderAccessRole.NO_ACCESS,
        )


async def test_folder_update(
    connection: SAConnection, setup_users_and_groups: set[_GroupID]
):
    owner_gid = _get_random_gid(setup_users_and_groups)
    other_owner_gid = _get_random_gid(
        setup_users_and_groups, already_picked={owner_gid}
    )
    editor_gid = _get_random_gid(
        setup_users_and_groups, already_picked={owner_gid, other_owner_gid}
    )
    viewer_gid = _get_random_gid(
        setup_users_and_groups, already_picked={owner_gid, other_owner_gid, editor_gid}
    )
    no_access_gid = _get_random_gid(
        setup_users_and_groups,
        already_picked={owner_gid, other_owner_gid, editor_gid, viewer_gid},
    )
    share_with_error_gid = _get_random_gid(
        setup_users_and_groups,
        already_picked={
            owner_gid,
            other_owner_gid,
            editor_gid,
            viewer_gid,
            no_access_gid,
        },
    )

    # 1. folder is missing
    missing_folder_id = 1231321332
    with pytest.raises(FolderNotFoundError):
        await folder_update(connection, missing_folder_id, owner_gid)
    await _assert_folder_entires(connection, folder_count=0)

    # 2. owner updates created fodler
    folder_id = await folder_create(connection, "f1", owner_gid)
    await _assert_folder_entires(connection, folder_count=1)
    await _assert_name_and_description(connection, folder_id, name="f1", description="")

    # nothing changes
    await folder_update(connection, folder_id, owner_gid)
    await _assert_name_and_description(connection, folder_id, name="f1", description="")

    # both changed
    await folder_update(
        connection, folder_id, owner_gid, name="new_folder", description="new_desc"
    )
    await _assert_name_and_description(
        connection, folder_id, name="new_folder", description="new_desc"
    )

    # 3. another_owner can also update
    await folder_share_or_update_permissions(
        connection,
        folder_id,
        sharing_gid=owner_gid,
        recipient_gid=other_owner_gid,
        recipient_role=FolderAccessRole.OWNER,
    )
    await folder_update(
        connection,
        folder_id,
        owner_gid,
        name="another_owner_name",
        description="another_owner_description",
    )
    await _assert_name_and_description(
        connection,
        folder_id,
        name="another_owner_name",
        description="another_owner_description",
    )

    # 4. other roles have no permission to update
    await folder_share_or_update_permissions(
        connection,
        folder_id,
        sharing_gid=owner_gid,
        recipient_gid=editor_gid,
        recipient_role=FolderAccessRole.EDITOR,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id,
        sharing_gid=owner_gid,
        recipient_gid=viewer_gid,
        recipient_role=FolderAccessRole.VIEWER,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id,
        sharing_gid=owner_gid,
        recipient_gid=no_access_gid,
        recipient_role=FolderAccessRole.NO_ACCESS,
    )

    for target_user_gid in (editor_gid, viewer_gid, no_access_gid):
        with pytest.raises(InsufficientPermissionsError):
            await folder_update(
                connection,
                folder_id,
                target_user_gid,
                name="error_name",
                description="error_description",
            )
        await _assert_name_and_description(
            connection,
            folder_id,
            name="another_owner_name",
            description="another_owner_description",
        )

    with pytest.raises(FolderNotSharedWithGidError):
        await folder_update(
            connection,
            folder_id,
            share_with_error_gid,
            name="error_name",
            description="error_description",
        )
    await _assert_name_and_description(
        connection,
        folder_id,
        name="another_owner_name",
        description="another_owner_description",
    )


async def test_folder_delete(
    connection: SAConnection, setup_users_and_groups: set[_GroupID]
):
    owner_gid = _get_random_gid(setup_users_and_groups)
    other_owner_gid = _get_random_gid(
        setup_users_and_groups, already_picked={owner_gid}
    )
    editor_gid = _get_random_gid(
        setup_users_and_groups, already_picked={owner_gid, other_owner_gid}
    )
    viewer_gid = _get_random_gid(
        setup_users_and_groups, already_picked={owner_gid, other_owner_gid, editor_gid}
    )
    no_access_gid = _get_random_gid(
        setup_users_and_groups,
        already_picked={owner_gid, other_owner_gid, editor_gid, viewer_gid},
    )
    share_with_error_gid = _get_random_gid(
        setup_users_and_groups,
        already_picked={
            owner_gid,
            other_owner_gid,
            editor_gid,
            viewer_gid,
            no_access_gid,
        },
    )

    # 1. folder is missing
    missing_folder_id = 1231321332
    with pytest.raises(FolderNotFoundError):
        await folder_delete(connection, missing_folder_id, owner_gid)
    await _assert_folder_entires(connection, folder_count=0)

    # 2. owner deletes folder
    folder_id = await folder_create(connection, "f1", owner_gid)
    await _assert_folder_entires(connection, folder_count=1)

    await folder_delete(connection, folder_id, owner_gid)
    await _assert_folder_entires(connection, folder_count=0)

    # 3. other owners can delete the folder
    folder_id = await folder_create(connection, "f1", owner_gid)
    await _assert_folder_entires(connection, folder_count=1)

    await folder_share_or_update_permissions(
        connection,
        folder_id,
        sharing_gid=owner_gid,
        recipient_gid=other_owner_gid,
        recipient_role=FolderAccessRole.OWNER,
    )

    await folder_delete(connection, folder_id, other_owner_gid)
    await _assert_folder_entires(connection, folder_count=0)

    # 4. non owner users cannot delete the folder
    folder_id = await folder_create(connection, "f1", owner_gid)
    await _assert_folder_entires(connection, folder_count=1)

    await folder_share_or_update_permissions(
        connection,
        folder_id,
        sharing_gid=owner_gid,
        recipient_gid=editor_gid,
        recipient_role=FolderAccessRole.EDITOR,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id,
        sharing_gid=owner_gid,
        recipient_gid=viewer_gid,
        recipient_role=FolderAccessRole.VIEWER,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id,
        sharing_gid=owner_gid,
        recipient_gid=no_access_gid,
        recipient_role=FolderAccessRole.NO_ACCESS,
    )
    await _assert_folder_entires(connection, folder_count=1, access_rights_count=4)

    for non_owner_gid in (editor_gid, viewer_gid, no_access_gid):
        with pytest.raises(InsufficientPermissionsError):
            await folder_delete(connection, folder_id, non_owner_gid)

    with pytest.raises(FolderNotSharedWithGidError):
        await folder_delete(connection, folder_id, share_with_error_gid)

    await _assert_folder_entires(connection, folder_count=1, access_rights_count=4)


async def test_folder_move(
    connection: SAConnection, setup_users_and_groups: set[_GroupID]
):
    gid_sharing = _get_random_gid(setup_users_and_groups)
    gid_user_a = _get_random_gid(setup_users_and_groups, already_picked={gid_sharing})
    gid_user_b = _get_random_gid(
        setup_users_and_groups, already_picked={gid_sharing, gid_user_a}
    )

    ################
    # CREATE FOLDERS
    ################

    # FOLDER STRUCTURE {`fodler_name`(`owner_gid`)[`shared_with_gid`, ...]}
    # `USER_SHARING`(`gid_sharing`)
    # `USER_A`(`gid_user_a`):
    #   - `f_user_a`
    # `USER_B`(`gid_user_b`):
    #   - `f_user_b`
    # `SHARED_AS_OWNER`(`gid_sharing`):
    #   - `f_shared_as_owner_user_a`[`gid_user_a`]
    #   - `f_shared_as_owner_user_b`[`gid_user_b`]
    # `SHARED_AS_EDITOR`(`gid_sharing`):
    #   - `f_shared_as_editor_user_a`[`gid_user_a`]
    #   - `f_shared_as_editor_user_b`[`gid_user_b`]
    # `SHARED_AS_VIEWER`(`gid_sharing`):
    #   - `f_shared_as_viewer_user_a`[`gid_user_a`]
    #   - `f_shared_as_viewer_user_b`[`gid_user_b`]
    # `SHARED_AS_NO_ACCESS`(`gid_sharing`):
    #   - `f_shared_as_no_access_user_a`[`gid_user_a`]
    #   - `f_shared_as_no_access_user_b`[`gid_user_b`]
    # `NOT_SHARED`(`gid_sharing`)

    # `USER_SHARING`
    folder_id_user_sharing = await folder_create(
        connection, "USER_SHARING", gid_sharing
    )

    # `USER_A` contains `f_user_a`
    folder_id_user_a = await folder_create(connection, "USER_A", gid_user_a)
    folder_id_f_user_a = await folder_create(
        connection, "f_user_a", gid_user_a, parent=folder_id_user_a
    )

    # `USER_B` contains `f_user_b`
    folder_id_user_b = await folder_create(connection, "USER_B", gid_user_b)
    folder_id_f_user_b = await folder_create(
        connection, "f_user_b", gid_user_b, parent=folder_id_user_b
    )

    # `SHARED_AS_OWNER` contains `f_shared_as_owner_user_a`, `f_shared_as_owner_user_b`
    folder_id_shared_as_owner = await folder_create(
        connection, "SHARED_AS_OWNER", gid_sharing
    )
    folder_id_f_shared_as_owner_user_a = await folder_create(
        connection,
        "f_shared_as_owner_user_a",
        gid_sharing,
        parent=folder_id_shared_as_owner,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id_f_shared_as_owner_user_a,
        gid_sharing,
        recipient_gid=gid_user_a,
        recipient_role=FolderAccessRole.OWNER,
    )
    folder_id_f_shared_as_owner_user_b = await folder_create(
        connection,
        "f_shared_as_owner_user_b",
        gid_sharing,
        parent=folder_id_shared_as_owner,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id_f_shared_as_owner_user_b,
        gid_sharing,
        recipient_gid=gid_user_b,
        recipient_role=FolderAccessRole.OWNER,
    )

    # `SHARED_AS_EDITOR` contains `f_shared_as_editor_user_a`, `f_shared_as_editor_user_b`
    folder_id_shared_as_editor = await folder_create(
        connection, "SHARED_AS_EDITOR", gid_sharing
    )
    folder_id_f_shared_as_editor_user_a = await folder_create(
        connection,
        "f_shared_as_editor_user_a",
        gid_sharing,
        parent=folder_id_shared_as_editor,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id_f_shared_as_editor_user_a,
        gid_sharing,
        recipient_gid=gid_user_a,
        recipient_role=FolderAccessRole.EDITOR,
    )
    folder_id_f_shared_as_editor_user_b = await folder_create(
        connection,
        "f_shared_as_editor_user_b",
        gid_sharing,
        parent=folder_id_shared_as_editor,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id_f_shared_as_editor_user_b,
        gid_sharing,
        recipient_gid=gid_user_b,
        recipient_role=FolderAccessRole.EDITOR,
    )

    # `SHARED_AS_VIEWER` contains `f_shared_as_viewer_user_a`, `f_shared_as_viewer_user_b`
    folder_id_shared_as_viewer = await folder_create(
        connection, "SHARED_AS_VIEWER", gid_sharing
    )
    folder_id_f_shared_as_viewer_user_a = await folder_create(
        connection,
        "f_shared_as_viewer_user_a",
        gid_sharing,
        parent=folder_id_shared_as_viewer,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id_f_shared_as_viewer_user_a,
        gid_sharing,
        recipient_gid=gid_user_a,
        recipient_role=FolderAccessRole.VIEWER,
    )
    folder_id_f_shared_as_viewer_user_b = await folder_create(
        connection,
        "f_shared_as_viewer_user_b",
        gid_sharing,
        parent=folder_id_shared_as_viewer,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id_f_shared_as_viewer_user_b,
        gid_sharing,
        recipient_gid=gid_user_b,
        recipient_role=FolderAccessRole.VIEWER,
    )

    # `SHARED_AS_NO_ACCESS` contains `f_shared_as_no_access_user_a`, `f_shared_as_no_access_user_b`
    folder_id_shared_as_no_access = await folder_create(
        connection, "SHARED_AS_NO_ACCESS", gid_sharing
    )
    folder_id_f_shared_as_no_access_user_a = await folder_create(
        connection,
        "f_shared_as_no_access_user_a",
        gid_sharing,
        parent=folder_id_shared_as_no_access,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id_f_shared_as_no_access_user_a,
        gid_sharing,
        recipient_gid=gid_user_a,
        recipient_role=FolderAccessRole.NO_ACCESS,
    )
    folder_id_f_shared_as_no_access_user_b = await folder_create(
        connection,
        "f_shared_as_no_access_user_b",
        gid_sharing,
        parent=folder_id_shared_as_no_access,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id_f_shared_as_no_access_user_b,
        gid_sharing,
        recipient_gid=gid_user_b,
        recipient_role=FolderAccessRole.NO_ACCESS,
    )

    # `NOT_SHARED`
    folder_id_not_shared = await folder_create(connection, "NOT_SHARED", gid_sharing)

    #######
    # TESTS
    #######
    async def _move_fails_not_shared_with_error(
        gid: _GroupID, *, source: _FolderID, destination: _FolderID
    ) -> None:
        with pytest.raises(FolderNotSharedWithGidError):
            await folder_move(
                connection,
                source,
                gid,
                destination_folder_id=destination,
            )

    async def _move_fails_insufficient_permissions_error(
        gid: _GroupID, *, source: _FolderID, destination: _FolderID
    ) -> None:
        with pytest.raises(InsufficientPermissionsError):
            await folder_move(
                connection,
                source,
                gid,
                destination_folder_id=destination,
            )

    async def _move_back_and_forth(
        gid: _GroupID,
        *,
        source: _FolderID,
        destination: _FolderID,
        source_parent: _FolderID,
    ) -> None:
        async def _assert_folder_permissions(
            connection: SAConnection,
            *,
            folder_id: _FolderID,
            gid: _GroupID,
            parent_folder: _FolderID,
        ) -> None:
            result = await connection.execute(
                sa.select([folders_access_rights.c.folder_id])
                .where(folders_access_rights.c.folder_id == folder_id)
                .where(folders_access_rights.c.gid == gid)
                .where(folders_access_rights.c.traversal_parent_id == parent_folder)
            )
            rows = await result.fetchall()
            assert rows is not None
            assert len(rows) == 1

        # check parent should be parent_before
        await _assert_folder_permissions(
            connection, folder_id=source, gid=gid, parent_folder=source_parent
        )

        await folder_move(
            connection,
            source,
            gid,
            destination_folder_id=destination,
        )

        # check parent should be destination
        await _assert_folder_permissions(
            connection, folder_id=source, gid=gid, parent_folder=destination
        )

        await folder_move(
            connection,
            source,
            gid,
            destination_folder_id=source_parent,
        )

        # check parent should be parent_before
        await _assert_folder_permissions(
            connection, folder_id=source, gid=gid, parent_folder=source_parent
        )

    # 1. not working:
    # - `USER_A/f_user_a -> USER_B`
    await _move_fails_not_shared_with_error(
        gid_user_a, source=folder_id_f_user_a, destination=folder_id_user_b
    )
    # - `USER_B.f_user_b -/> USER_A`
    await _move_fails_not_shared_with_error(
        gid_user_b, source=folder_id_f_user_b, destination=folder_id_user_a
    )
    # - `USER_A/f_user_a -> NOT_SHARED`
    await _move_fails_not_shared_with_error(
        gid_user_a, source=folder_id_f_user_a, destination=folder_id_not_shared
    )
    # - `USER_B/f_user_b -> NOT_SHARED`
    await _move_fails_not_shared_with_error(
        gid_user_b, source=folder_id_f_user_b, destination=folder_id_not_shared
    )
    # - `USER_A/f_user_a -> f_shared_as_no_access_user_a`
    await _move_fails_insufficient_permissions_error(
        gid_user_a,
        source=folder_id_f_user_a,
        destination=folder_id_f_shared_as_no_access_user_a,
    )
    # - `USER_B/f_user_b -> f_shared_as_no_access_user_b`
    await _move_fails_insufficient_permissions_error(
        gid_user_b,
        source=folder_id_f_user_b,
        destination=folder_id_f_shared_as_no_access_user_b,
    )
    # - `USER_A/f_user_a -> f_shared_as_viewer_user_a`
    await _move_fails_insufficient_permissions_error(
        gid_user_a,
        source=folder_id_f_user_a,
        destination=folder_id_f_shared_as_viewer_user_a,
    )
    # - `USER_B/f_user_b -> f_shared_as_viewer_user_b`
    await _move_fails_insufficient_permissions_error(
        gid_user_b,
        source=folder_id_f_user_b,
        destination=folder_id_f_shared_as_viewer_user_b,
    )

    # 2. allowed oeprations:
    # - `USER_A/f_user_a -> f_shared_as_editor_user_a` (& reverse)
    await _move_back_and_forth(
        gid_user_a,
        source=folder_id_f_user_a,
        destination=folder_id_f_shared_as_editor_user_a,
        source_parent=folder_id_user_a,
    )
    # - `USER_B/f_user_b -> f_shared_as_editor_user_b` (& reverse)
    await _move_back_and_forth(
        gid_user_b,
        source=folder_id_f_user_b,
        destination=folder_id_f_shared_as_editor_user_b,
        source_parent=folder_id_user_b,
    )
    # - `USER_A/f_user_a -> f_shared_as_owner_user_a` (& reverse)
    await _move_back_and_forth(
        gid_user_a,
        source=folder_id_f_user_a,
        destination=folder_id_f_shared_as_owner_user_a,
        source_parent=folder_id_user_a,
    )
    # - `USER_B/f_user_b -> f_shared_as_owner_user_b` (& reverse)
    await _move_back_and_forth(
        gid_user_b,
        source=folder_id_f_user_b,
        destination=folder_id_f_shared_as_owner_user_b,
        source_parent=folder_id_user_b,
    )


async def test_move_only_owners_can_move(
    connection: SAConnection, setup_users_and_groups: set[_GroupID]
):
    gid_owner = _get_random_gid(setup_users_and_groups)
    gid_editor = _get_random_gid(setup_users_and_groups, already_picked={gid_owner})
    gid_viewer = _get_random_gid(
        setup_users_and_groups, already_picked={gid_owner, gid_editor}
    )
    gid_no_access = _get_random_gid(
        setup_users_and_groups, already_picked={gid_owner, gid_editor, gid_viewer}
    )
    gid_not_shared = _get_random_gid(
        setup_users_and_groups,
        already_picked={gid_owner, gid_editor, gid_viewer, gid_no_access},
    )

    # FOLDER STRUCTURE {`fodler_name`(`owner_gid`)[`shared_with_gid`, ...]}
    # `to_move`(`gid_owner`)[`gid_editor`,`gid_viewer`,`gid_no_access`]
    # `target_owner`(`gid_owner`)
    # `target_editor`(`gid_editor`)
    # `target_viewer`(`gid_viewer`)
    # `target_no_access`(`gid_no_access`)
    # `target_not_shared`(`gid_not_shared`)
    folder_id_to_move = await folder_create(connection, "to_move", gid_owner)
    await folder_share_or_update_permissions(
        connection,
        folder_id_to_move,
        gid_owner,
        recipient_gid=gid_editor,
        recipient_role=FolderAccessRole.EDITOR,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id_to_move,
        gid_owner,
        recipient_gid=gid_viewer,
        recipient_role=FolderAccessRole.VIEWER,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id_to_move,
        gid_owner,
        recipient_gid=gid_no_access,
        recipient_role=FolderAccessRole.NO_ACCESS,
    )

    folder_id_target_owner = await folder_create(connection, "target_owner", gid_owner)
    folder_id_target_editor = await folder_create(
        connection, "target_editor", gid_editor
    )
    folder_id_target_viewer = await folder_create(
        connection, "target_viewer", gid_viewer
    )
    folder_id_target_no_access = await folder_create(
        connection, "target_no_access", gid_no_access
    )
    folder_id_target_not_shared = await folder_create(
        connection, "target_not_shared", gid_not_shared
    )

    async def _fails_to_move(gid: _GroupID, destination_folder_id: _FolderID) -> None:
        with pytest.raises(InsufficientPermissionsError):
            await folder_move(
                connection,
                folder_id_to_move,
                gid,
                destination_folder_id=destination_folder_id,
            )

    # 1. no permissions to move
    await _fails_to_move(gid_editor, folder_id_target_editor)
    await _fails_to_move(gid_viewer, folder_id_target_viewer)
    await _fails_to_move(gid_no_access, folder_id_target_no_access)

    # 2. not shared with user
    with pytest.raises(FolderNotSharedWithGidError):
        await folder_move(
            connection,
            folder_id_to_move,
            gid_not_shared,
            destination_folder_id=folder_id_target_not_shared,
        )

    # 3. owner us able to move
    await folder_move(
        connection,
        folder_id_to_move,
        gid_owner,
        destination_folder_id=folder_id_target_owner,
    )


async def test_move_group_non_standard_groups_raise_error(
    connection: SAConnection,
    setup_users_and_groups: set[_GroupID],
    create_fake_group: Callable[..., Awaitable[RowProxy]],
):
    gid_sharing = _get_random_gid(setup_users_and_groups)
    gid_primary = (await create_fake_group(connection, type=GroupType.PRIMARY)).gid
    gid_everyone = await connection.scalar(
        sa.select([groups.c.gid]).where(groups.c.type == GroupType.EVERYONE)
    )
    assert gid_everyone
    gid_standard = (await create_fake_group(connection, type=GroupType.STANDARD)).gid

    # FOLDER STRUCTURE {`fodler_name`(`owner_gid`)[`shared_with_gid`, ...]}
    # `SHARING_USER`(`gid_sharing`)[`gid_primary`,`gid_everyone`,`gid_standard`]
    # `PRIMARY`(`gid_primary`)
    # `EVERYONE`(`gid_everyone`)
    # `STANDARD`(`gid_standard`)

    folder_id_sharing_user = await folder_create(
        connection, "SHARING_USER", gid_sharing
    )
    for gid_to_share_with in (gid_primary, gid_everyone, gid_standard):
        await folder_share_or_update_permissions(
            connection,
            folder_id_sharing_user,
            gid_sharing,
            recipient_gid=gid_to_share_with,
            recipient_role=FolderAccessRole.EDITOR,
        )
    folder_id_primary = await folder_create(connection, "PRIMARY", gid_primary)
    folder_id_everyone = await folder_create(connection, "EVERYONE", gid_everyone)
    folder_id_standard = await folder_create(connection, "STANDARD", gid_standard)

    with pytest.raises(CannotMoveFolderSharedViaNonPrimaryGroupError) as exc:
        await folder_move(
            connection,
            folder_id_everyone,
            gid_everyone,
            destination_folder_id=folder_id_sharing_user,
        )
    assert "EVERYONE" in f"{exc.value}"

    with pytest.raises(CannotMoveFolderSharedViaNonPrimaryGroupError) as exc:
        await folder_move(
            connection,
            folder_id_standard,
            gid_standard,
            destination_folder_id=folder_id_sharing_user,
        )
    assert "STANDARD" in f"{exc.value}"

    # primary gorup does not raise error
    await folder_move(
        connection,
        folder_id_primary,
        gid_primary,
        destination_folder_id=folder_id_sharing_user,
    )


async def test_add_remove_project_in_folder(
    connection: SAConnection,
    setup_users_and_groups: set[_GroupID],
    setup_projects_for_users: set[_ProjectID],
):
    async def _is_project_present(
        connection: SAConnection,
        folder_id: _FolderID,
        project_id: _ProjectID,
    ) -> bool:
        async with connection.execute(
            folders_to_projects.select()
            .where(folders_to_projects.c.folder_id == folder_id)
            .where(folders_to_projects.c.project_id == project_id)
        ) as result:
            rows = await result.fetchall()
            assert rows is not None
            return len(rows) == 1

    gid_owner = _get_random_gid(setup_users_and_groups)
    gid_editor = _get_random_gid(setup_users_and_groups, already_picked={gid_owner})
    gid_viewer = _get_random_gid(
        setup_users_and_groups, already_picked={gid_owner, gid_editor}
    )
    gid_no_access = _get_random_gid(
        setup_users_and_groups, already_picked={gid_owner, gid_editor, gid_viewer}
    )
    project_id = _get_random_project_id(setup_projects_for_users)

    # SETUP
    folder_id = await folder_create(connection, "f1", gid_owner)
    await folder_share_or_update_permissions(
        connection,
        folder_id,
        gid_owner,
        recipient_gid=gid_editor,
        recipient_role=FolderAccessRole.EDITOR,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id,
        gid_owner,
        recipient_gid=gid_viewer,
        recipient_role=FolderAccessRole.VIEWER,
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id,
        gid_owner,
        recipient_gid=gid_no_access,
        recipient_role=FolderAccessRole.NO_ACCESS,
    )

    async def _add_folder_as(gid: _GroupID) -> None:
        await folder_add_project(connection, folder_id, gid, project_id=project_id)
        assert await _is_project_present(connection, folder_id, project_id) is True

    async def _remove_folder_as(gid: _GroupID) -> None:
        await folder_remove_project(connection, folder_id, gid, project_id=project_id)
        assert await _is_project_present(connection, folder_id, project_id) is False

    assert await _is_project_present(connection, folder_id, project_id) is False

    # 1. owner can add and remove
    await _add_folder_as(gid_owner)
    await _remove_folder_as(gid_owner)

    # 2 editor can add and can't remove
    await _add_folder_as(gid_editor)
    with pytest.raises(InsufficientPermissionsError):
        await _remove_folder_as(gid_editor)
    await _remove_folder_as(gid_owner)  # cleanup

    # 3. viwer can't add and can't remove
    with pytest.raises(InsufficientPermissionsError):
        await _add_folder_as(gid_viewer)
    with pytest.raises(InsufficientPermissionsError):
        await _remove_folder_as(gid_viewer)

    # 4. no_access can't add and can't remove
    with pytest.raises(InsufficientPermissionsError):
        await _add_folder_as(gid_no_access)
    with pytest.raises(InsufficientPermissionsError):
        await _remove_folder_as(gid_no_access)


class ExpectedValues(NamedTuple):
    id: _FolderID
    access_via_gid: _GroupID
    my_access_rights: _FolderPermissions
    access_rights: dict[_GroupID, _FolderPermissions]

    def __hash__(self):
        return hash(
            (
                self.id,
                self.access_via_gid,
                tuple(sorted(self.my_access_rights.items())),
                tuple(
                    (k, tuple(sorted(v.items())))
                    for k, v in sorted(self.access_rights.items())
                ),
            )
        )

    def __eq__(self, other):
        if not isinstance(other, ExpectedValues):
            return False
        return (
            self.id == other.id
            and self.access_via_gid == other.access_via_gid
            and self.my_access_rights == other.my_access_rights
            and self.access_rights == other.access_rights
        )


def _assert_expected_entries(
    folders: list[FolderEntry], *, expected: set[ExpectedValues]
) -> None:
    for folder_entry in folders:
        expected_values = ExpectedValues(
            folder_entry.id,
            folder_entry.access_via_gid,
            folder_entry.my_access_rights,
            folder_entry.access_rights,
        )
        assert expected_values in expected


ALL_IN_ONE_PAGE_OFFSET: NonNegativeInt = 0
ALL_IN_ONE_PAGE_LIMIT: NonNegativeInt = 1000


async def _list_folder_as(
    connection: SAConnection,
    folder_id: _FolderID | None,
    gid: _GroupID,
    offset: NonNegativeInt = ALL_IN_ONE_PAGE_OFFSET,
    limit: NonNegativeInt = ALL_IN_ONE_PAGE_LIMIT,
) -> list[FolderEntry]:

    return await folder_list(
        connection,
        folder_id,
        gid,
        offset=offset,
        limit=limit,
    )


async def test_folder_list(
    connection: SAConnection, setup_users_and_groups: set[_GroupID]
):
    gid_owner = _get_random_gid(setup_users_and_groups)
    gid_editor = _get_random_gid(setup_users_and_groups, already_picked={gid_owner})
    gid_viewer = _get_random_gid(
        setup_users_and_groups, already_picked={gid_owner, gid_editor}
    )
    gid_no_access = _get_random_gid(
        setup_users_and_groups, already_picked={gid_owner, gid_editor, gid_viewer}
    )
    gid_not_shared = _get_random_gid(
        setup_users_and_groups,
        already_picked={gid_owner, gid_editor, gid_viewer, gid_no_access},
    )

    # FOLDER STRUCTURE {`fodler_name`(`owner_gid`)[`shared_with_gid`, ...]}
    # `owner_folder`(`gid_owner`)[`gid_editor`,`gid_viewer`,`gid_no_access`]:
    #   - `f1`(`gid_owner`)
    #   - `f2`(`gid_owner`)
    #   - `f3`(`gid_owner`)
    #   - `f4`(`gid_owner`)
    #   - `f5`(`gid_owner`)
    #   - `f6`(`gid_owner`)
    #   - `f7`(`gid_owner`)
    #   - `f8`(`gid_owner`)
    #   - `f9`(`gid_owner`)
    #   - `f10`(`gid_owner`):
    #       - `sub_f1`(`gid_owner`)
    #       - `sub_f2`(`gid_owner`)
    #       - `sub_f3`(`gid_owner`)
    #       - `sub_f4`(`gid_owner`)
    #       - `sub_f5`(`gid_owner`)
    #       - `sub_f6`(`gid_owner`)
    #       - `sub_f7`(`gid_owner`)
    #       - `sub_f8`(`gid_owner`)
    #       - `sub_f9`(`gid_owner`)
    #       - `sub_f10`(`gid_owner`)

    folder_id_owner_folder = await folder_create(connection, "owner_folder", gid_owner)
    for recipient_gid, recipient_role in [
        (gid_editor, FolderAccessRole.EDITOR),
        (gid_viewer, FolderAccessRole.VIEWER),
        (gid_no_access, FolderAccessRole.NO_ACCESS),
    ]:
        await folder_share_or_update_permissions(
            connection,
            folder_id_owner_folder,
            gid_owner,
            recipient_gid=recipient_gid,
            recipient_role=recipient_role,
        )
    folder_id_f1 = await folder_create(
        connection, "f1", gid_owner, parent=folder_id_owner_folder
    )
    folder_id_f2 = await folder_create(
        connection, "f2", gid_owner, parent=folder_id_owner_folder
    )
    folder_id_f3 = await folder_create(
        connection, "f3", gid_owner, parent=folder_id_owner_folder
    )
    folder_id_f4 = await folder_create(
        connection, "f4", gid_owner, parent=folder_id_owner_folder
    )
    folder_id_f5 = await folder_create(
        connection, "f5", gid_owner, parent=folder_id_owner_folder
    )
    folder_id_f6 = await folder_create(
        connection, "f6", gid_owner, parent=folder_id_owner_folder
    )
    folder_id_f7 = await folder_create(
        connection, "f7", gid_owner, parent=folder_id_owner_folder
    )
    folder_id_f8 = await folder_create(
        connection, "f8", gid_owner, parent=folder_id_owner_folder
    )
    folder_id_f9 = await folder_create(
        connection, "f9", gid_owner, parent=folder_id_owner_folder
    )
    folder_id_f10 = await folder_create(
        connection, "f10", gid_owner, parent=folder_id_owner_folder
    )

    folder_id_sub_f1 = await folder_create(
        connection, "sub_f1", gid_owner, parent=folder_id_f10
    )
    folder_id_sub_f2 = await folder_create(
        connection, "sub_f2", gid_owner, parent=folder_id_f10
    )
    folder_id_sub_f3 = await folder_create(
        connection, "sub_f3", gid_owner, parent=folder_id_f10
    )
    folder_id_sub_f4 = await folder_create(
        connection, "sub_f4", gid_owner, parent=folder_id_f10
    )
    folder_id_sub_f5 = await folder_create(
        connection, "sub_f5", gid_owner, parent=folder_id_f10
    )
    folder_id_sub_f6 = await folder_create(
        connection, "sub_f6", gid_owner, parent=folder_id_f10
    )
    folder_id_sub_f7 = await folder_create(
        connection, "sub_f7", gid_owner, parent=folder_id_f10
    )
    folder_id_sub_f8 = await folder_create(
        connection, "sub_f8", gid_owner, parent=folder_id_f10
    )
    folder_id_sub_f9 = await folder_create(
        connection, "sub_f9", gid_owner, parent=folder_id_f10
    )
    folder_id_sub_f10 = await folder_create(
        connection, "sub_f10", gid_owner, parent=folder_id_f10
    )

    ALL_FOLDERS_FX = (
        folder_id_f1,
        folder_id_f2,
        folder_id_f3,
        folder_id_f4,
        folder_id_f5,
        folder_id_f6,
        folder_id_f7,
        folder_id_f8,
        folder_id_f9,
        folder_id_f10,
    )

    ALL_FOLDERS_SUB_FX = (
        folder_id_sub_f1,
        folder_id_sub_f2,
        folder_id_sub_f3,
        folder_id_sub_f4,
        folder_id_sub_f5,
        folder_id_sub_f6,
        folder_id_sub_f7,
        folder_id_sub_f8,
        folder_id_sub_f9,
        folder_id_sub_f10,
    )

    ALL_FOLDERS_AND_SUBFOLDERS = (
        folder_id_owner_folder,
        *ALL_FOLDERS_FX,
        *ALL_FOLDERS_SUB_FX,
    )

    # TESTS

    ACCESS_RIGHTS_BY_GID: dict[_GroupID, _FolderPermissions] = {
        gid_owner: OWNER_PERMISSIONS,
        gid_editor: EDITOR_PERMISSIONS,
        gid_viewer: VIEWER_PERMISSIONS,
        gid_no_access: NO_ACCESS_PERMISSIONS,
    }

    # 1. list all levels per gid with access
    for listing_gid in (gid_owner, gid_editor, gid_viewer):
        # list `root` for gid
        _assert_expected_entries(
            await _list_folder_as(connection, None, listing_gid),
            expected={
                ExpectedValues(
                    folder_id_owner_folder,
                    listing_gid,
                    ACCESS_RIGHTS_BY_GID[listing_gid],
                    {
                        gid_owner: OWNER_PERMISSIONS,
                        gid_editor: EDITOR_PERMISSIONS,
                        gid_viewer: VIEWER_PERMISSIONS,
                        gid_no_access: NO_ACCESS_PERMISSIONS,
                    },
                ),
            },
        )
        # list `owner_folder` for gid
        _assert_expected_entries(
            await _list_folder_as(connection, folder_id_owner_folder, listing_gid),
            expected={
                ExpectedValues(
                    fx,
                    listing_gid,
                    ACCESS_RIGHTS_BY_GID[listing_gid],
                    {gid_owner: OWNER_PERMISSIONS},
                )
                for fx in ALL_FOLDERS_FX
            },
        )
        # list `f10` for gid
        _assert_expected_entries(
            await _list_folder_as(connection, folder_id_f10, listing_gid),
            expected={
                ExpectedValues(
                    sub_fx,
                    listing_gid,
                    ACCESS_RIGHTS_BY_GID[listing_gid],
                    {gid_owner: OWNER_PERMISSIONS},
                )
                for sub_fx in ALL_FOLDERS_SUB_FX
            },
        )

    # 2. lisit all levels for `gid_no_access`
    # can always be ran but should not list any entry
    _assert_expected_entries(
        await _list_folder_as(connection, None, gid_no_access), expected=set()
    )
    # there are insusficient permissions
    for folder_id_to_check in ALL_FOLDERS_AND_SUBFOLDERS:
        with pytest.raises(InsufficientPermissionsError):
            await _list_folder_as(connection, folder_id_to_check, gid_no_access)

    # 3. lisit all levels for `gid_not_shared``
    # can always list the contets of the "root" folder for a gid
    _assert_expected_entries(
        await _list_folder_as(connection, None, gid_not_shared), expected=set()
    )
    for folder_id_to_check in ALL_FOLDERS_AND_SUBFOLDERS:
        with pytest.raises(FolderNotSharedWithGidError):
            await _list_folder_as(connection, folder_id_to_check, gid_not_shared)

    # 4. list with pagination
    for initial_limit in (1, 2, 3, 4, 5):
        offset = 0
        limit = initial_limit
        found_folders: list[FolderEntry] = []
        while items := await _list_folder_as(
            connection, folder_id_owner_folder, gid_owner, offset=offset, limit=limit
        ):
            found_folders.extend(items)
            offset += limit
            if len(items) != limit:
                break

        one_shot_query = await _list_folder_as(
            connection, folder_id_owner_folder, gid_owner
        )

        assert len(found_folders) == len(one_shot_query)
        assert found_folders == one_shot_query


async def test_folder_list_shared_with_different_permissions(
    connection: SAConnection, setup_users_and_groups: set[_GroupID]
):
    gid_owner_a = _get_random_gid(setup_users_and_groups)
    gid_owner_b = _get_random_gid(setup_users_and_groups, already_picked={gid_owner_a})
    gid_owner_c = _get_random_gid(
        setup_users_and_groups, already_picked={gid_owner_a, gid_owner_b}
    )
    gid_owner_level_2 = _get_random_gid(
        setup_users_and_groups, already_picked={gid_owner_a, gid_owner_b, gid_owner_c}
    )

    # FOLDER STRUCTURE {`fodler_name`(`owner_gid`)[`shared_with_gid`, ...]}
    # `f_owner_a`(`gid_owner_a`)[`gid_owner_b`,`gid_owner_c`]:
    #   - `f_owner_b`(`gid_owner_b`):
    #       - `f_owner_c`(`gid_owner_c`)[`gid_owner_level_2`]:
    #           - `f_sub_owner_c`(`gid_owner_c`)
    #           - `f_owner_level_2`(`gid_owner_level_2`)
    folder_id_f_owner_a = await folder_create(connection, "f_owner_a", gid_owner_a)
    for target_gid in (gid_owner_b, gid_owner_c):
        await folder_share_or_update_permissions(
            connection,
            folder_id_f_owner_a,
            gid_owner_a,
            recipient_gid=target_gid,
            recipient_role=FolderAccessRole.OWNER,
        )
    folder_id_f_owner_b = await folder_create(
        connection, "f_owner_b", gid_owner_b, parent=folder_id_f_owner_a
    )
    folder_id_f_owner_c = await folder_create(
        connection, "f_owner_c", gid_owner_c, parent=folder_id_f_owner_b
    )
    await folder_share_or_update_permissions(
        connection,
        folder_id_f_owner_c,
        gid_owner_c,
        recipient_gid=gid_owner_level_2,
        recipient_role=FolderAccessRole.OWNER,
    )
    folder_id_f_sub_owner_c = await folder_create(
        connection, "f_sub_owner_c", gid_owner_c, parent=folder_id_f_owner_c
    )
    folder_id_f_owner_level_2 = await folder_create(
        connection, "f_owner_level_2", gid_owner_level_2, parent=folder_id_f_owner_c
    )

    # 1. `gid_owner_a`, `gid_owner_b`, `gid_owner_c` have the exact same veiw
    for listing_gid in (gid_owner_a, gid_owner_b, gid_owner_c):
        # list `root` for gid
        _assert_expected_entries(
            await _list_folder_as(connection, None, listing_gid),
            expected={
                ExpectedValues(
                    folder_id_f_owner_a,
                    listing_gid,
                    OWNER_PERMISSIONS,
                    {
                        gid_owner_a: OWNER_PERMISSIONS,
                        gid_owner_b: OWNER_PERMISSIONS,
                        gid_owner_c: OWNER_PERMISSIONS,
                    },
                ),
            },
        )
        # list `f_owner_a` for gid
        _assert_expected_entries(
            await _list_folder_as(connection, folder_id_f_owner_a, listing_gid),
            expected={
                ExpectedValues(
                    folder_id_f_owner_b,
                    listing_gid,
                    OWNER_PERMISSIONS,
                    {gid_owner_b: OWNER_PERMISSIONS},
                ),
            },
        )
        # list `f_owner_b` for gid
        _assert_expected_entries(
            await _list_folder_as(connection, folder_id_f_owner_b, listing_gid),
            expected={
                ExpectedValues(
                    folder_id_f_owner_c,
                    listing_gid,
                    OWNER_PERMISSIONS,
                    {
                        gid_owner_c: OWNER_PERMISSIONS,
                        gid_owner_level_2: OWNER_PERMISSIONS,
                    },
                ),
            },
        )
        # list `f_owner_c` for gid
        _assert_expected_entries(
            await _list_folder_as(connection, folder_id_f_owner_c, listing_gid),
            expected={
                ExpectedValues(
                    folder_id_f_sub_owner_c,
                    listing_gid,
                    OWNER_PERMISSIONS,
                    {
                        gid_owner_c: OWNER_PERMISSIONS,
                    },
                ),
                ExpectedValues(
                    folder_id_f_owner_level_2,
                    listing_gid,
                    OWNER_PERMISSIONS,
                    {
                        gid_owner_level_2: OWNER_PERMISSIONS,
                    },
                ),
            },
        )

    # 2. `gid_owner_level_2` can only access from `f_owner_c` downwards
    # list `f_owner_c` for `gid_owner_level_2`
    _assert_expected_entries(
        await _list_folder_as(connection, None, gid_owner_level_2),
        expected={
            ExpectedValues(
                folder_id_f_owner_c,
                gid_owner_level_2,
                OWNER_PERMISSIONS,
                {
                    gid_owner_c: OWNER_PERMISSIONS,
                    gid_owner_level_2: OWNER_PERMISSIONS,
                },
            ),
        },
    )
    # list `root` for `gid_owner_level_2`
    _assert_expected_entries(
        await _list_folder_as(connection, folder_id_f_owner_c, gid_owner_level_2),
        expected={
            ExpectedValues(
                folder_id_f_sub_owner_c,
                gid_owner_level_2,
                OWNER_PERMISSIONS,
                {
                    gid_owner_c: OWNER_PERMISSIONS,
                },
            ),
            ExpectedValues(
                folder_id_f_owner_level_2,
                gid_owner_level_2,
                OWNER_PERMISSIONS,
                {
                    gid_owner_level_2: OWNER_PERMISSIONS,
                },
            ),
        },
    )
