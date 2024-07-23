import re
import uuid
from collections.abc import Iterable
from enum import Enum
from functools import reduce
from typing import ClassVar, Final, TypeAlias, TypedDict

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from psycopg2.errors import ForeignKeyViolation
from pydantic import NonNegativeInt, PositiveInt
from pydantic.errors import PydanticErrorMixin
from sqlalchemy.sql.elements import ColumnElement

from .models.folders import folders, folders_access_rights

_ProjectID: TypeAlias = uuid.UUID
_GroupID: TypeAlias = PositiveInt
_FolderID: TypeAlias = PositiveInt

###
### ERRORS
###


# TODO: add error hierarchy here


class FoldersError(PydanticErrorMixin, RuntimeError):
    pass


class InvalidFolderNameError(FoldersError):
    msg_template = "Provided folder name='{name}' is invalid: {reason}"


class BaseCreateFlderError(FoldersError):
    """used as base"""


class FolderAlreadyExistsError(BaseCreateFlderError):
    msg_template = (
        "A folder='{folder}' with parent='{parent}' for group='{gid}' already exists"
    )


class ParentFolderIsNotWritableError(BaseCreateFlderError):
    msg_template = "Cannot create any sub-folders inside folder_id={parent_folder_id} since it is not writable for gid={gid}."


class CouldNotCreateFolderError(BaseCreateFlderError):
    msg_template = "Could not create folder='{folder}' and parent='{parent}'"


class GroupIdDoesNotExistError(BaseCreateFlderError):
    msg_template = "Provided group id '{gid}' does not exist "


###
### UTILS ACCESS LAYER
###


class FolderAccessRole(Enum):
    """Used by the frontend to indicate a role in a simple manner"""

    VIEWER = 0
    EDITOR = 1
    OWNER = 2


class _FolderPermissions(TypedDict):
    read: bool
    write: bool
    delete: bool


def _make_permissions(
    *, r: bool = False, w: bool = False, d: bool = False, description: str = ""
) -> "_FolderPermissions":
    _ = description
    return _FolderPermissions(read=r, write=w, delete=d)


_ALL_PERMISSION_KEYS: Final[set[str]] = {"read", "write", "delete"}


def _or_reduce(x: _FolderPermissions, y: _FolderPermissions) -> _FolderPermissions:
    return {key: x[key] or y[key] for key in _ALL_PERMISSION_KEYS}


def _or_dicts_list(dicts: Iterable[_FolderPermissions]) -> _FolderPermissions:
    if not dicts:
        return _make_permissions()
    return reduce(_or_reduce, dicts)


class _BasePermissions:
    LIST_FOLDERS: ClassVar[_FolderPermissions] = _make_permissions(r=True)
    LIST_PROJECTS: ClassVar[_FolderPermissions] = _make_permissions(r=True)

    CREATE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(w=True)
    ADD_PROJECT_TO_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(w=True)

    _MOVE_FOLDER_SOURCE: ClassVar[_FolderPermissions] = _make_permissions(
        r=True, description="apply to folder form which data is copied"
    )
    _MOVE_FOLDER_TARGET: ClassVar[_FolderPermissions] = _make_permissions(
        w=True, description="apply to folder to which data will be copied"
    )
    MOVE_VOLDER: ClassVar[_FolderPermissions] = _or_dicts_list(
        [_MOVE_FOLDER_SOURCE, _MOVE_FOLDER_TARGET]
    )

    SHARE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    RENAME_FODLER: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    EDIT_FOLDER_DESCRIPTION: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    DELETE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    DELETE_PROJECT_FROM_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)


VIEWER_PERMISSIONS: _FolderPermissions = _or_dicts_list(
    [
        _BasePermissions.LIST_FOLDERS,
        _BasePermissions.LIST_PROJECTS,
    ]
)
EDITOR_PERMISSIONS: _FolderPermissions = _or_dicts_list(
    [
        VIEWER_PERMISSIONS,
        _BasePermissions.CREATE_FOLDER,
        _BasePermissions.ADD_PROJECT_TO_FOLDER,
        _BasePermissions.MOVE_VOLDER,
    ]
)
OWNER_PERMISSIONS: _FolderPermissions = _or_dicts_list(
    [
        EDITOR_PERMISSIONS,
        _BasePermissions.SHARE_FOLDER,
        _BasePermissions.RENAME_FODLER,
        _BasePermissions.EDIT_FOLDER_DESCRIPTION,
        _BasePermissions.DELETE_FOLDER,
        _BasePermissions.DELETE_PROJECT_FROM_FOLDER,
    ]
)

_PERMISSIONS_BY_ROLE: dict[FolderAccessRole, _FolderPermissions] = {
    FolderAccessRole.VIEWER: VIEWER_PERMISSIONS,
    FolderAccessRole.EDITOR: EDITOR_PERMISSIONS,
    FolderAccessRole.OWNER: OWNER_PERMISSIONS,
}


def _get_permissions_from_role(role: FolderAccessRole) -> _FolderPermissions:
    return _PERMISSIONS_BY_ROLE[role]


def _requires(*permissions: _FolderPermissions):
    if len(permissions) == 0:
        return _make_permissions()
    return _or_dicts_list(permissions)


def _get_where_clause(permissions: _FolderPermissions) -> ColumnElement | bool:
    clauses: list[ColumnElement] = []

    if permissions["read"]:
        clauses.append(folders_access_rights.c.read.is_(True))
    if permissions["write"]:
        clauses.append(folders_access_rights.c.write.is_(True))
    if permissions["delete"]:
        clauses.append(folders_access_rights.c.delete.is_(True))

    return sa.and_(*clauses) if clauses else True


###
### UTILS NAMING
###

_RE_FOLDER_NAME_INVALID_CHARS: Final[str] = r'[<>:"/\\|?*]'
_FOLDER_NAMES_RESERVED_WINDOWS: Final[set[str]] = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *[f"COM{i}" for i in range(1, 10)],
    *[f"LPT{i}" for i in range(1, 10)],
}
_FOLDER_NAME_MAX_LENGTH: Final[NonNegativeInt] = 255


def _validate_folder_name(value: str) -> None:
    if not value:
        raise InvalidFolderNameError(name=value, reason="folder cannot be empty")

    if re.search(_RE_FOLDER_NAME_INVALID_CHARS, value):
        reason = f"name contains invalid characters. Must comply to regex={_RE_FOLDER_NAME_INVALID_CHARS}"
        raise InvalidFolderNameError(name=value, reason=reason)

    if value.upper() in _FOLDER_NAMES_RESERVED_WINDOWS:
        raise InvalidFolderNameError(
            name=value,
            reason=f"name is a reserved word in Windows. Can't be any of the following: {_FOLDER_NAMES_RESERVED_WINDOWS}",
        )

    if len(value) > _FOLDER_NAME_MAX_LENGTH:
        raise InvalidFolderNameError(
            name=value,
            reason=f"name is too long. Maximum length is {_FOLDER_NAME_MAX_LENGTH} characters",
        )


###
### DB LAYER API
###


async def create_folder(
    connection: SAConnection,
    name: str,
    gid: _GroupID,
    *,
    description: str = "",
    parent: _FolderID | None = None,
    required_permissions: _FolderPermissions = _requires(  # noqa: B008
        _BasePermissions.CREATE_FOLDER
    ),
) -> _FolderID:
    _validate_folder_name(name)

    async with connection.begin():
        entry_exists: int | None = await connection.scalar(
            sa.select([folders.c.id])
            .select_from(
                folders.join(
                    folders_access_rights,
                    folders.c.id == folders_access_rights.c.folder_id,
                )
            )
            .where(folders.c.name == name)
            .where(folders_access_rights.c.gid == gid)
            .where(folders_access_rights.c.parent_folder == parent)
        )
        if entry_exists:
            raise FolderAlreadyExistsError(folder=name, parent=parent, gid=gid)

        if parent:
            # NOTE: read access is not required in order to write
            has_write_access_in_parent: int | None = await connection.scalar(
                sa.select([folders_access_rights.c.folder_id])
                .where(folders_access_rights.c.folder_id == parent)
                .where(folders_access_rights.c.gid == gid)
                .where(_get_where_clause(required_permissions))
            )
            if not has_write_access_in_parent:
                raise ParentFolderIsNotWritableError(parent_folder_id=parent, gid=gid)

        # folder entry can now be inserted
        try:
            folder_id = await connection.scalar(
                sa.insert(folders)
                .values(name=name, description=description, owner=gid)
                .returning(folders.c.id)
            )

            if not folder_id:
                raise CouldNotCreateFolderError(folder=name, parent=parent)

            await connection.execute(
                sa.insert(folders_access_rights).values(
                    folder_id=folder_id,
                    gid=gid,
                    parent_folder=parent,
                    **OWNER_PERMISSIONS,
                )
            )
        except ForeignKeyViolation as e:
            raise GroupIdDoesNotExistError(gid=gid) from e

        return _FolderID(folder_id)


# TODO: add the following
# - create folder
# - delete folder
# - move folder
# - add project in folder
# - remove project form folder
# - still need a way to compute permissions (for now we do a basic thing, only list our own permissions)
# - listing is on matus
