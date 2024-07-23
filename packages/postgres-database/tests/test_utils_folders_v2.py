from unittest.mock import Mock

import pytest
from simcore_postgres_database.utils_folders_v2 import (
    _FOLDER_NAME_MAX_LENGTH,
    _FOLDER_NAMES_RESERVED_WINDOWS,
    _PERMISSIONS_BY_ROLE,
    EDITOR_PERMISSIONS,
    OWNER_PERMISSIONS,
    VIEWER_PERMISSIONS,
    FolderAccessRole,
    InvalidFolderNameError,
    _FolderPermissions,
    _get_permissions_from_role,
    _get_where_clause,
    _requires,
    create_folder,
)
from sqlalchemy.sql.elements import ColumnElement


def test_permissions_integrity():
    assert set(FolderAccessRole) == set(_PERMISSIONS_BY_ROLE.keys())


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
    assert isinstance(_get_where_clause(VIEWER_PERMISSIONS), ColumnElement)
    assert isinstance(_get_where_clause(EDITOR_PERMISSIONS), ColumnElement)
    assert isinstance(_get_where_clause(OWNER_PERMISSIONS), ColumnElement)
    assert isinstance(
        _get_where_clause({"read": False, "write": False, "delete": False}), bool
    )


# TODO: write down some tests for this
# - utils for craeting entries in DB for -> groups that can be VIEWER, EDITOR, OWNER
