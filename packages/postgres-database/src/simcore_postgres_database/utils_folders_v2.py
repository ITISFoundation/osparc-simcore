import re
import uuid
from enum import Enum
from functools import reduce
from typing import ClassVar, Final, Iterable, TypeAlias, TypedDict

from aiopg.sa.connection import SAConnection
from pydantic import NonNegativeInt, PositiveInt
from pydantic.errors import PydanticErrorMixin

_ProjectID: TypeAlias = uuid.UUID
_GroupID: TypeAlias = PositiveInt
_FolderID: TypeAlias = PositiveInt

###
### ERRORS
###


class FoldersError(PydanticErrorMixin, RuntimeError):
    pass


class InvalidFolderNameError(FoldersError):
    msg_template = "Provided folder name='{name}' is invalid: {reason}"


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


class _BasePermissions:
    LIST_FOLDERS: ClassVar[_FolderPermissions] = _make_permissions(r=True)
    LIST_PROJECTS: ClassVar[_FolderPermissions] = _make_permissions(r=True)

    CREATE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(w=True)
    ADD_PROJECT_TO_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(w=True)
    MOVE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(
        r=True, w=True, description="source (r=True), target (w=True)"
    )

    SHARE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    RENAME_FODLER: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    EDIT_FOLDER_DESCRIPTION: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    DELETE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    DELETE_PROJECT_FROM_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)


_ALL_PERMISSION_KEYS: Final[set[str]] = {"read", "write", "delete"}


def _or_reduce(x: _FolderPermissions, y: _FolderPermissions) -> _FolderPermissions:
    return {key: x[key] or y[key] for key in _ALL_PERMISSION_KEYS}


def _or_dicts_list(dicts: Iterable[_FolderPermissions]) -> _FolderPermissions:
    if not dicts:
        return _make_permissions()
    return reduce(_or_reduce, dicts)


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
        _BasePermissions.MOVE_FOLDER,
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


def _requires_permissions(*permissions: _FolderPermissions):
    if len(permissions) == 0:
        return _make_permissions()
    return _or_dicts_list(permissions)


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
    required_permissions: _FolderPermissions = _requires_permissions(
        _BasePermissions.CREATE_FOLDER
    ),
) -> None:
    _validate_folder_name(name)
