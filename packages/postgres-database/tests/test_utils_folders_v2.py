# pylint:disable=redefined-outer-name

import secrets
from collections.abc import Awaitable, Callable
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from pydantic import NonNegativeInt
from simcore_postgres_database.models.folders import folders, folders_access_rights
from simcore_postgres_database.utils_folders_v2 import (
    _FOLDER_NAME_MAX_LENGTH,
    _FOLDER_NAMES_RESERVED_WINDOWS,
    _ROLE_TO_PERMISSIONS,
    EDITOR_PERMISSIONS,
    OWNER_PERMISSIONS,
    VIEWER_PERMISSIONS,
    FolderAccessRole,
    FolderAlreadyExistsError,
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
    create_folder,
    folder_delete,
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
        await create_folder(Mock(), invalid_name, Mock())


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


async def test_create_folder(
    connection: SAConnection, setup_users_and_groups: set[_GroupID]
):
    owner_gid = _get_random_gid(setup_users_and_groups)

    # when GID is missing no entries should be present
    missing_gid = 10202023302
    await _assert_folder_entires(connection, folder_count=0)
    with pytest.raises(GroupIdDoesNotExistError):
        await create_folder(connection, "f1", missing_gid)
    await _assert_folder_entires(connection, folder_count=0)

    # create a folder ana subfolder of the same name
    f1_folder_id = await create_folder(connection, "f1", owner_gid)
    await _assert_folder_entires(connection, folder_count=1)
    await create_folder(connection, "f1", owner_gid, parent=f1_folder_id)
    await _assert_folder_entires(connection, folder_count=2)

    # inserting already existing folder fails
    with pytest.raises(FolderAlreadyExistsError):
        await create_folder(connection, "f1", owner_gid)
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
    root_folder_id = await create_folder(connection, "root_folder", owner_a_gid)
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
    b_folder_id = await create_folder(
        connection, "b_folder", owner_b_gid, parent=root_folder_id
    )
    c_folder_id = await create_folder(
        connection, "c_folder", owner_c_gid, parent=root_folder_id
    )
    d_folder_id = await create_folder(
        connection, "d_folder", owner_d_gid, parent=c_folder_id
    )
    editor_a_folder_id = await create_folder(
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

    # Folder structure: `FOLDER_NAME(OWNER)[SHARED_WITH]`:
    # - root_folder(owner_a)[owner_b,owner_c,owner_d, editor_a]
    #   - b_folder(owner_b)
    #   - c_folder(owner_c):
    #       - d_folder(owner_d)[editor_b]:
    #           - editor_a_folder(editor_a)

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

    # TODO: we need a test when the sharing of a folder happens with someone it needs to reoslve properly with the new owner and not others

    # TODO: after moving is added add a test to test that this till works when parents are changed


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
    folder_id = await create_folder(connection, "f1", owner_gid)
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
    folder_id = await create_folder(connection, "f1", owner_gid)
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
    folder_id = await create_folder(connection, "f1", owner_gid)
    await _assert_folder_entires(connection, folder_count=1)

    await folder_delete(connection, folder_id, owner_gid)
    await _assert_folder_entires(connection, folder_count=0)

    # 3. other owners can delete the folder
    folder_id = await create_folder(connection, "f1", owner_gid)
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
    folder_id = await create_folder(connection, "f1", owner_gid)
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
