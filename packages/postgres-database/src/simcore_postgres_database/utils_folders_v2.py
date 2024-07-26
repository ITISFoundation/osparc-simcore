import re
import uuid
from collections.abc import Iterable
from datetime import datetime
from enum import Enum
from functools import reduce
from typing import Any, ClassVar, Final, TypeAlias, TypedDict

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from psycopg2.errors import ForeignKeyViolation
from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt
from pydantic.errors import PydanticErrorMixin
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import ColumnElement

from .models.folders import folders, folders_access_rights, folders_to_projects
from .models.groups import GroupType, groups

_ProjectID: TypeAlias = uuid.UUID
_GroupID: TypeAlias = PositiveInt
_FolderID: TypeAlias = PositiveInt

###
### ERRORS
###


"""Errors hierarcy

FoldersError
    * InvalidFolderNameError
    * BaseAccessError
        * FolderNotFoundError
        * FolderNotSharedWithGidError
        * InsufficientPermissionsError
    * BaseCreateFlderError
        * FolderAlreadyExistsError
        * ParentFolderIsNotWritableError
        * CouldNotCreateFolderError
        * GroupIdDoesNotExistError
    * BaseMoveFolderError
        * CannotMoveFolderSharedViaNonPrimaryGroupError
    * BaseAddProjectError
        * ProjectAlreadyExistsInFolderError
"""


class FoldersError(PydanticErrorMixin, RuntimeError):
    pass


class InvalidFolderNameError(FoldersError):
    msg_template = "Provided folder name='{name}' is invalid: {reason}"


class BaseAccessError(FoldersError):
    pass


class FolderNotFoundError(BaseAccessError):
    msg_template = "no entry for folder_id={folder_id} found"


class FolderNotSharedWithGidError(BaseAccessError):
    msg_template = "folder_id={folder_id} was not shared with gid={gid}"


class InsufficientPermissionsError(BaseAccessError):
    msg_template = "could not find a parent for folder_id={folder_id} and gid={gid}, with permissions={permissions}"


class BaseCreateFlderError(FoldersError):
    pass


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


class BaseMoveFolderError(FoldersError):
    pass


class CannotMoveFolderSharedViaNonPrimaryGroupError(BaseMoveFolderError):
    msg_template = (
        "deltected group_type={group_type} for gid={gid} which is not allowed"
    )


class BaseAddProjectError(FoldersError):
    pass


class ProjectAlreadyExistsInFolderError(BaseAddProjectError):
    msg_template = "project_id={project_id} in folder_id={folder_id} is already present"


###
### UTILS ACCESS LAYER
###


class FolderAccessRole(Enum):
    """Used by the frontend to indicate a role in a simple manner"""

    NO_ACCESS = 0
    VIEWER = 1
    EDITOR = 2
    OWNER = 3


class _FolderPermissions(TypedDict):
    read: bool
    write: bool
    delete: bool


def _make_permissions(
    *, r: bool = False, w: bool = False, d: bool = False, description: str = ""
) -> "_FolderPermissions":
    _ = description
    return _FolderPermissions(read=r, write=w, delete=d)


def _only_true_permissions(permissions: _FolderPermissions) -> dict:
    return {k: v for k, v in permissions.items() if v is True}


_ALL_PERMISSION_KEYS: Final[set[str]] = {"read", "write", "delete"}


def _or_reduce(x: _FolderPermissions, y: _FolderPermissions) -> _FolderPermissions:
    return _FolderPermissions(**{key: x[key] or y[key] for key in _ALL_PERMISSION_KEYS})


def _or_dicts_list(dicts: Iterable[_FolderPermissions]) -> _FolderPermissions:
    if not dicts:
        return _make_permissions()
    return reduce(_or_reduce, dicts)


class _BasePermissions:
    LIST_FOLDERS: ClassVar[_FolderPermissions] = _make_permissions(r=True)
    # NOTE `LIST_PROJECTS` bypasses these access rights and always lists all projects in the fodler

    CREATE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(w=True)
    ADD_PROJECT_TO_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(w=True)

    SHARE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    UPDATE_FODLER: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    DELETE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    REMOVE_PROJECT_FROM_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)

    _MOVE_FOLDER_SOURCE: ClassVar[_FolderPermissions] = _make_permissions(
        d=True,
        description="apply to folder form which data is copied",
    )
    _MOVE_FOLDER_DESTINATION: ClassVar[_FolderPermissions] = _make_permissions(
        w=True, description="apply to folder to which data will be copied"
    )
    MOVE_FOLDER: ClassVar[_FolderPermissions] = _or_dicts_list(
        [_MOVE_FOLDER_SOURCE, _MOVE_FOLDER_DESTINATION]
    )


NO_ACCESS_PERMISSIONS: _FolderPermissions = _make_permissions()

VIEWER_PERMISSIONS: _FolderPermissions = _or_dicts_list(
    [
        _BasePermissions.LIST_FOLDERS,
    ]
)
EDITOR_PERMISSIONS: _FolderPermissions = _or_dicts_list(
    [
        VIEWER_PERMISSIONS,
        _BasePermissions.CREATE_FOLDER,
        _BasePermissions.ADD_PROJECT_TO_FOLDER,
    ]
)
OWNER_PERMISSIONS: _FolderPermissions = _or_dicts_list(
    [
        EDITOR_PERMISSIONS,
        _BasePermissions.SHARE_FOLDER,
        _BasePermissions.UPDATE_FODLER,
        _BasePermissions.DELETE_FOLDER,
        _BasePermissions.REMOVE_PROJECT_FROM_FOLDER,
        _BasePermissions.MOVE_FOLDER,
    ]
)

_ROLE_TO_PERMISSIONS: dict[FolderAccessRole, _FolderPermissions] = {
    FolderAccessRole.NO_ACCESS: NO_ACCESS_PERMISSIONS,
    FolderAccessRole.VIEWER: VIEWER_PERMISSIONS,
    FolderAccessRole.EDITOR: EDITOR_PERMISSIONS,
    FolderAccessRole.OWNER: OWNER_PERMISSIONS,
}


def _hash_permissions(permissions: _FolderPermissions) -> tuple:
    return tuple(permissions.items())


_PERMISSIONS_TO_ROLE: dict[tuple, FolderAccessRole] = {
    _hash_permissions(NO_ACCESS_PERMISSIONS): FolderAccessRole.NO_ACCESS,
    _hash_permissions(VIEWER_PERMISSIONS): FolderAccessRole.VIEWER,
    _hash_permissions(EDITOR_PERMISSIONS): FolderAccessRole.EDITOR,
    _hash_permissions(OWNER_PERMISSIONS): FolderAccessRole.OWNER,
}


def _get_permissions_from_role(role: FolderAccessRole) -> _FolderPermissions:
    return _ROLE_TO_PERMISSIONS[role]


def _get_role_from_permissions(permissions: _FolderPermissions) -> FolderAccessRole:
    return _PERMISSIONS_TO_ROLE[_hash_permissions(permissions)]


def _requires(*permissions: _FolderPermissions):
    if len(permissions) == 0:
        return _make_permissions()
    return _or_dicts_list(permissions)


def _get_true_permissions(
    permissions: _FolderPermissions, table
) -> ColumnElement | bool:
    """compose SQL where clause where only for the entries that are True"""
    clauses: list[ColumnElement] = []

    if permissions["read"]:
        clauses.append(table.c.read.is_(True))
    if permissions["write"]:
        clauses.append(table.c.write.is_(True))
    if permissions["delete"]:
        clauses.append(table.c.delete.is_(True))

    return sa.and_(*clauses) if clauses else True


def _get_all_permissions(permissions: _FolderPermissions, table) -> ColumnElement:
    return sa.and_(
        table.c.read.is_(permissions["read"]),
        table.c.write.is_(permissions["write"]),
        table.c.delete.is_(permissions["delete"]),
    )


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


class FolderEntry(BaseModel):
    id: _FolderID
    parent_folder: _FolderID | None = Field(alias="traversal_parent_id")
    name: str
    description: str
    owner: _GroupID = Field(alias="created_by")
    created_at: datetime
    last_modified: datetime
    my_access_rights: _FolderPermissions
    access_rights: dict[_GroupID, _FolderPermissions]

    access_via_gid: _GroupID = Field(
        ...,
        description="used to compute my_access_rights, should be used by the frotned",
    )
    gid: _GroupID = Field(..., description="actual gid of this entry")

    class Config:
        orm_mode = True


async def _get_top_most_access_rights_entry(
    connection: SAConnection,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    permissions: _FolderPermissions | None,
    enforece_all_permissions: bool,
) -> RowProxy | None:

    # Define the anchor CTE
    access_rights_cte = (
        sa.select(
            [
                folders_access_rights.c.folder_id,
                folders_access_rights.c.gid,
                folders_access_rights.c.traversal_parent_id,
                folders_access_rights.c.original_parent_id,
                folders_access_rights.c.read,
                folders_access_rights.c.write,
                folders_access_rights.c.delete,
                sa.literal_column("0").label("level"),
            ]
        )
        .where(folders_access_rights.c.folder_id == sa.bindparam("start_folder_id"))
        .cte(name="access_rights_cte", recursive=True)
    )

    # Define the recursive part of the CTE
    recursive = sa.select(
        [
            folders_access_rights.c.folder_id,
            folders_access_rights.c.gid,
            folders_access_rights.c.traversal_parent_id,
            folders_access_rights.c.original_parent_id,
            folders_access_rights.c.read,
            folders_access_rights.c.write,
            folders_access_rights.c.delete,
            sa.literal_column("access_rights_cte.level + 1").label("level"),
        ]
    ).select_from(
        folders_access_rights.join(
            access_rights_cte,
            folders_access_rights.c.folder_id == access_rights_cte.c.original_parent_id,
        )
    )

    # Combine anchor and recursive CTE
    folder_hierarchy = access_rights_cte.union_all(recursive)

    # Final query to filter and order results
    query = (
        sa.select(
            [
                folder_hierarchy.c.folder_id,
                folder_hierarchy.c.gid,
                folder_hierarchy.c.traversal_parent_id,
                folder_hierarchy.c.original_parent_id,
                folder_hierarchy.c.read,
                folder_hierarchy.c.write,
                folder_hierarchy.c.delete,
                folder_hierarchy.c.level,
            ]
        )
        .where(
            (
                _get_all_permissions(permissions, folder_hierarchy)
                if enforece_all_permissions
                else _get_true_permissions(permissions, folder_hierarchy)
            )
            if permissions
            else True
        )
        .where(folder_hierarchy.c.original_parent_id.is_(None))
        .where(folder_hierarchy.c.gid == gid)
        .order_by(folder_hierarchy.c.level.asc())
    )

    result = await connection.execute(query.params(start_folder_id=folder_id))
    top_most_parent: RowProxy | None = await result.fetchone()
    return top_most_parent


async def _check_folder_and_access(
    connection: SAConnection,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    permissions: _FolderPermissions,
    enforece_all_permissions: bool,
) -> RowProxy:
    """
    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
    """
    folder_entry: int | None = await connection.scalar(
        sa.select([folders.c.id]).where(folders.c.id == folder_id)
    )
    if not folder_entry:
        raise FolderNotFoundError(folder_id=folder_id)

    # check if folder was shared
    top_most_access_rights_without_permissions = (
        await _get_top_most_access_rights_entry(
            connection,
            folder_id,
            gid,
            permissions=None,
            enforece_all_permissions=False,
        )
    )
    if not top_most_access_rights_without_permissions:
        raise FolderNotSharedWithGidError(folder_id=folder_id, gid=gid)

    # check if there are permissions
    top_most_parent_with_permissions = await _get_top_most_access_rights_entry(
        connection,
        folder_id,
        gid,
        permissions=permissions,
        enforece_all_permissions=enforece_all_permissions,
    )
    if top_most_parent_with_permissions is None:
        raise InsufficientPermissionsError(
            folder_id=folder_id,
            gid=gid,
            permissions=_only_true_permissions(permissions),
        )

    return top_most_parent_with_permissions


async def folder_create(
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
    """
    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
        FolderAlreadyExistsError
        CouldNotCreateFolderError
        GroupIdDoesNotExistError
    """
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
            .where(folders_access_rights.c.original_parent_id == parent)
        )
        if entry_exists:
            raise FolderAlreadyExistsError(folder=name, parent=parent, gid=gid)

        if parent:
            # check if parent has permissions
            await _check_folder_and_access(
                connection,
                folder_id=parent,
                gid=gid,
                permissions=required_permissions,
                enforece_all_permissions=False,
            )

        # folder entry can now be inserted
        try:
            folder_id = await connection.scalar(
                sa.insert(folders)
                .values(name=name, description=description, created_by=gid)
                .returning(folders.c.id)
            )

            if not folder_id:
                raise CouldNotCreateFolderError(folder=name, parent=parent)

            await connection.execute(
                sa.insert(folders_access_rights).values(
                    folder_id=folder_id,
                    gid=gid,
                    traversal_parent_id=parent,
                    original_parent_id=parent,
                    **OWNER_PERMISSIONS,
                )
            )
        except ForeignKeyViolation as e:
            raise GroupIdDoesNotExistError(gid=gid) from e

        return _FolderID(folder_id)


async def folder_share_or_update_permissions(
    connection: SAConnection,
    folder_id: _FolderID,
    sharing_gid: _GroupID,
    *,
    recipient_gid: _GroupID,
    recipient_role: FolderAccessRole,
    required_permissions: _FolderPermissions = _requires(  # noqa: B008
        _BasePermissions.SHARE_FOLDER
    ),
) -> None:
    """
    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
    """
    # NOTE: if the `sharing_gid`` has permissions to share it can share it with any `FolderAccessRole`
    async with connection.begin():
        await _check_folder_and_access(
            connection,
            folder_id=folder_id,
            gid=sharing_gid,
            permissions=required_permissions,
            enforece_all_permissions=False,
        )

        # update or create permissions entry
        sharing_permissions: _FolderPermissions = _get_permissions_from_role(
            recipient_role
        )
        data: dict[str, Any] = {
            "folder_id": folder_id,
            "gid": recipient_gid,
            "original_parent_id": None,
            "traversal_parent_id": None,
            **sharing_permissions,
        }
        insert_stmt = postgresql.insert(folders_access_rights).values(**data)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[
                folders_access_rights.c.folder_id,
                folders_access_rights.c.gid,
            ],
            set_=data,
        )
        await connection.execute(upsert_stmt)


async def folder_update(
    connection: SAConnection,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    name: str | None = None,
    description: str | None = None,
    required_permissions: _FolderPermissions = _requires(  # noqa: B008
        _BasePermissions.UPDATE_FODLER
    ),
) -> None:
    """
    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
    """
    async with connection.begin():
        await _check_folder_and_access(
            connection,
            folder_id=folder_id,
            gid=gid,
            permissions=required_permissions,
            enforece_all_permissions=False,
        )

        # do not update if nothing changed
        if name is None and description is None:
            return

        values: dict[str, str] = {}
        if name:
            values["name"] = name
        if description:
            values["description"] = description

        # update entry
        await connection.execute(
            folders.update().where(folders.c.id == folder_id).values(**values)
        )


async def folder_delete(
    connection: SAConnection,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    required_permissions: _FolderPermissions = _requires(  # noqa: B008
        _BasePermissions.DELETE_FOLDER
    ),
) -> None:
    """
    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
    """
    childern_folder_ids: list[_FolderID] = []

    async with connection.begin():
        await _check_folder_and_access(
            connection,
            folder_id=folder_id,
            gid=gid,
            permissions=required_permissions,
            enforece_all_permissions=False,
        )

        # list all children then delete
        results = await connection.execute(
            folders_access_rights.select()
            .where(folders_access_rights.c.traversal_parent_id == folder_id)
            .where(folders_access_rights.c.gid == gid)
        )
        rows = await results.fetchall()
        if rows:
            for entry in rows:
                childern_folder_ids.append(entry.folder_id)  # noqa: PERF401

        # directly remove folder, access rigths will be dropped as well
        await connection.execute(folders.delete().where(folders.c.id == folder_id))

    # finally remove all the children from the folder
    for child_folder_id in childern_folder_ids:
        await folder_delete(connection, child_folder_id, gid)


async def folder_move(
    connection: SAConnection,
    source_folder_id: _FolderID,
    gid: _GroupID,
    *,
    destination_folder_id: _FolderID,
    required_permissions_source: _FolderPermissions = _requires(  # noqa: B008
        _BasePermissions._MOVE_FOLDER_SOURCE  # pylint:disable=protected-access # noqa: SLF001
    ),
    required_permissions_destination: _FolderPermissions = _requires(  # noqa: B008
        _BasePermissions._MOVE_FOLDER_DESTINATION  # pylint:disable=protected-access # noqa: SLF001
    ),
) -> None:
    """
    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
        CannotMoveFolderSharedViaNonPrimaryGroupError:
    """
    async with connection.begin():
        source_access_entry = await _check_folder_and_access(
            connection,
            folder_id=source_folder_id,
            gid=gid,
            permissions=required_permissions_source,
            enforece_all_permissions=False,
        )

        source_access_gid = source_access_entry["gid"]
        group_type: GroupType | None = await connection.scalar(
            sa.select([groups.c.type]).where(groups.c.gid == source_access_gid)
        )
        if group_type is None or group_type != GroupType.PRIMARY:
            raise CannotMoveFolderSharedViaNonPrimaryGroupError(
                group_type=group_type, gid=source_access_gid
            )

        await _check_folder_and_access(
            connection,
            folder_id=destination_folder_id,
            gid=gid,
            permissions=required_permissions_destination,
            enforece_all_permissions=False,
        )

        # set new traversa_parent_id on the source_folder_id which is equal to destination_folder_id
        await connection.execute(
            folders_access_rights.update()
            .where(
                sa.and_(
                    folders_access_rights.c.folder_id == source_folder_id,
                    folders_access_rights.c.gid == gid,
                )
            )
            .values(traversal_parent_id=destination_folder_id)
        )


async def folder_add_project(
    connection: SAConnection,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    project_id: _ProjectID,
    required_permissions=_requires(  # noqa: B008
        _BasePermissions.ADD_PROJECT_TO_FOLDER
    ),
) -> None:
    """
    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
        ProjectAlreadyExistsInFolderError
    """
    async with connection.begin():
        await _check_folder_and_access(
            connection,
            folder_id=folder_id,
            gid=gid,
            permissions=required_permissions,
            enforece_all_permissions=False,
        )

        # check if already added in folder
        project_in_folder_entry = await (
            await connection.execute(
                folders_to_projects.select()
                .where(folders_to_projects.c.folder_id == folder_id)
                .where(folders_to_projects.c.project_id == project_id)
            )
        ).fetchone()
        if project_in_folder_entry:
            raise ProjectAlreadyExistsInFolderError(
                project_id=project_id, folder_id=folder_id
            )

        # finally add project to folder
        await connection.execute(
            folders_to_projects.insert().values(
                folder_id=folder_id, project_id=project_id
            )
        )


async def folder_remove_project(
    connection: SAConnection,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    project_id: _ProjectID,
    required_permissions=_requires(  # noqa: B008
        _BasePermissions.REMOVE_PROJECT_FROM_FOLDER
    ),
) -> None:
    """
    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
    """
    async with connection.begin():
        await _check_folder_and_access(
            connection,
            folder_id=folder_id,
            gid=gid,
            permissions=required_permissions,
            enforece_all_permissions=False,
        )

        await connection.execute(
            folders_to_projects.delete()
            .where(folders_to_projects.c.folder_id == folder_id)
            .where(folders_to_projects.c.project_id == project_id)
        )


async def folder_list(
    connection: SAConnection,
    folder_id: _FolderID | None,
    gid: _GroupID,
    *,
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    required_permissions=_requires(_BasePermissions.LIST_FOLDERS),  # noqa: B008
) -> list[FolderEntry]:
    """
    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
    """
    # NOTE: when `folder_id is None` list the root folder of `gid`

    results: list[FolderEntry] = []

    async with connection.begin():
        access_via_gid: _GroupID = gid
        access_via_folder_id: _FolderID | None = None

        if folder_id:
            # this one provides the set of access rights
            top_most_parent_with_permissions = await _check_folder_and_access(
                connection,
                folder_id=folder_id,
                gid=gid,
                permissions=required_permissions,
                enforece_all_permissions=False,
            )
            access_via_gid = top_most_parent_with_permissions["gid"]
            access_via_folder_id = top_most_parent_with_permissions["folder_id"]

        subquery_my_access_rights = (
            sa.select(
                sa.func.jsonb_build_object(
                    "read",
                    folders_access_rights.c.read,
                    "write",
                    folders_access_rights.c.write,
                    "delete",
                    folders_access_rights.c.delete,
                ).label("my_access_rights"),
            )
            .where(
                folders_access_rights.c.folder_id == access_via_folder_id
                if access_via_gid and access_via_folder_id
                else folders_access_rights.c.folder_id == folders.c.id
            )
            .where(folders_access_rights.c.gid == access_via_gid)
            .correlate(folders)
            .scalar_subquery()
        )

        subquery_access_rights = (
            sa.select(
                sa.func.jsonb_object_agg(
                    folders_access_rights.c.gid,
                    sa.func.jsonb_build_object(
                        "read",
                        folders_access_rights.c.read,
                        "write",
                        folders_access_rights.c.write,
                        "delete",
                        folders_access_rights.c.delete,
                    ),
                ).label("access_rights"),
            )
            .where(folders_access_rights.c.folder_id == folders.c.id)
            .correlate(folders)
            .scalar_subquery()
        )

        query = (
            sa.select(
                folders,
                folders_access_rights,
                sa.literal_column(f"{access_via_gid}").label("access_via_gid"),
                subquery_my_access_rights.label("my_access_rights"),
                subquery_access_rights.label("access_rights"),
            )
            .join(
                folders_access_rights, folders.c.id == folders_access_rights.c.folder_id
            )
            .where(
                folders_access_rights.c.traversal_parent_id.is_(None)
                if folder_id is None
                else folders_access_rights.c.traversal_parent_id == folder_id
            )
            .where(
                folders_access_rights.c.gid == access_via_gid
                if folder_id is None
                else True
            )
            .where(
                _get_true_permissions(required_permissions, folders_access_rights)
                if folder_id is None
                else True
            )
            .offset(offset)
            .limit(limit)
        )

        async for entry in connection.execute(query):
            results.append(FolderEntry.from_orm(entry))  # noqa: PERF401s

    return results
