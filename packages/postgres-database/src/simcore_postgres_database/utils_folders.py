import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import reduce
from typing import Any, ClassVar, TypeAlias

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from psycopg2.errors import ForeignKeyViolation
from pydantic import (
    BaseModel,
    ConstrainedStr,
    Field,
    NonNegativeInt,
    PositiveInt,
    parse_obj_as,
)
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


"""Errors hierarchy

FoldersError
    * InvalidFolderNameError
    * FolderAccessError
        * FolderNotFoundError
        * FolderNotSharedWithGidError
        * InsufficientPermissionsError
    * BaseCreateFolderError
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


class FolderAccessError(FoldersError):
    pass


class FolderNotFoundError(FolderAccessError):
    msg_template = "no entry for folder_id={folder_id} found"


class FolderNotSharedWithGidError(FolderAccessError):
    msg_template = "folder_id={folder_id} was not shared with gid={gid}"


class InsufficientPermissionsError(FolderAccessError):
    msg_template = "could not find a parent for folder_id={folder_id} and gid={gid}, with permissions={permissions}"


class BaseCreateFolderError(FoldersError):
    pass


class FolderAlreadyExistsError(BaseCreateFolderError):
    msg_template = (
        "A folder='{folder}' with parent='{parent}' for group='{gid}' already exists"
    )


class ParentFolderIsNotWritableError(BaseCreateFolderError):
    msg_template = "Cannot create any sub-folders inside folder_id={parent_folder_id} since it is not writable for gid={gid}."


class CouldNotCreateFolderError(BaseCreateFolderError):
    msg_template = "Could not create folder='{folder}' and parent='{parent}'"


class GroupIdDoesNotExistError(BaseCreateFolderError):
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
    msg_template = (
        "project_id={project_uuid} in folder_id={folder_id} is already present"
    )


###
### UTILS ACCESS LAYER
###


class FolderAccessRole(Enum):
    """Used by the frontend to indicate a role in a simple manner"""

    NO_ACCESS = 0
    VIEWER = 1
    EDITOR = 2
    OWNER = 3


@dataclass(frozen=True)
class _FolderPermissions:
    read: bool
    write: bool
    delete: bool

    def to_dict(self, *, include_only_true: bool = False) -> dict[str, bool]:
        data: dict[str, bool] = {
            "read": self.read,
            "write": self.write,
            "delete": self.delete,
        }
        if include_only_true:
            for key_to_remove in [k for k, v in data.items() if not v]:
                data.pop(key_to_remove)

        return data


def _make_permissions(
    *, r: bool = False, w: bool = False, d: bool = False, description: str = ""
) -> "_FolderPermissions":
    _ = description
    return _FolderPermissions(read=r, write=w, delete=d)


def _only_true_permissions(permissions: _FolderPermissions) -> dict:
    return permissions.to_dict(include_only_true=True)


def _or_reduce(x: _FolderPermissions, y: _FolderPermissions) -> _FolderPermissions:
    return _FolderPermissions(
        read=x.read or y.read, write=x.write or y.write, delete=x.delete or y.delete
    )


def _or_dicts_list(dicts: Iterable[_FolderPermissions]) -> _FolderPermissions:
    if not dicts:
        return _make_permissions()
    return reduce(_or_reduce, dicts)


class _BasePermissions:
    LIST_FOLDERS: ClassVar[_FolderPermissions] = _make_permissions(r=True)

    CREATE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(w=True)
    ADD_PROJECT_TO_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(w=True)

    SHARE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    UPDATE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    DELETE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    REMOVE_PROJECT_FROM_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)

    _MOVE_FOLDER_SOURCE: ClassVar[_FolderPermissions] = _make_permissions(
        d=True,
        description="apply to folder providing the data",
    )
    _MOVE_FOLDER_DESTINATION: ClassVar[_FolderPermissions] = _make_permissions(
        w=True, description="apply on the folder receiving the data"
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
        _BasePermissions.UPDATE_FOLDER,
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


def _get_permissions_from_role(role: FolderAccessRole) -> _FolderPermissions:
    return _ROLE_TO_PERMISSIONS[role]


def _requires(*permissions: _FolderPermissions) -> _FolderPermissions:
    if len(permissions) == 0:
        return _make_permissions()
    return _or_dicts_list(permissions)


def _get_true_permissions(
    permissions: _FolderPermissions, table
) -> ColumnElement | bool:
    """compose SQL where clause where only for the entries that are True"""
    clauses: list[ColumnElement] = []

    if permissions.read:
        clauses.append(table.c.read.is_(True))
    if permissions.write:
        clauses.append(table.c.write.is_(True))
    if permissions.delete:
        clauses.append(table.c.delete.is_(True))

    return sa.and_(*clauses) if clauses else True


def _get_all_permissions(permissions: _FolderPermissions, table) -> ColumnElement:
    return sa.and_(
        table.c.read.is_(permissions.read),
        table.c.write.is_(permissions.write),
        table.c.delete.is_(permissions.delete),
    )


###
### UTILS
###


class FolderName(ConstrainedStr):
    regex = re.compile(
        r'^(?!.*[<>:"/\\|?*\]])(?!.*\b(?:LPT9|COM1|LPT1|COM2|LPT3|LPT4|CON|COM5|COM3|COM4|AUX|PRN|LPT2|LPT5|COM6|LPT7|NUL|COM8|LPT6|COM9|COM7|LPT8)\b).+$',
        re.IGNORECASE,
    )
    min_length = 1
    max_length = 255


class FolderEntry(BaseModel):
    id: _FolderID
    parent_folder: _FolderID | None = Field(alias="traversal_parent_id")
    name: str
    description: str
    owner: _GroupID = Field(alias="created_by")
    created: datetime = Field(alias="selected_created")
    modified: datetime = Field(alias="selected_modified")
    my_access_rights: _FolderPermissions
    access_rights: dict[_GroupID, _FolderPermissions]

    access_via_gid: _GroupID = Field(
        ...,
        description="used to compute my_access_rights, should be used by the frotned",
    )
    gid: _GroupID = Field(..., description="actual gid of this entry")

    class Config:
        orm_mode = True


class _ResolvedAccessRights(BaseModel):
    folder_id: _FolderID
    gid: _GroupID
    traversal_parent_id: _FolderID | None
    original_parent_id: _FolderID | None
    read: bool
    write: bool
    delete: bool
    level: int

    class Config:
        orm_mode = True


async def _get_resolved_access_rights(
    connection: SAConnection,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    permissions: _FolderPermissions | None,
    enforece_all_permissions: bool,
) -> _ResolvedAccessRights | None:

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
    resolved_access_rights: RowProxy | None = await result.fetchone()
    return (
        _ResolvedAccessRights.from_orm(resolved_access_rights)
        if resolved_access_rights
        else None
    )


async def _check_folder_and_access(
    connection: SAConnection,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    permissions: _FolderPermissions,
    enforece_all_permissions: bool,
) -> _ResolvedAccessRights:
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
    resolved_access_rights_without_permissions = await _get_resolved_access_rights(
        connection,
        folder_id,
        gid,
        permissions=None,
        enforece_all_permissions=False,
    )
    if not resolved_access_rights_without_permissions:
        raise FolderNotSharedWithGidError(folder_id=folder_id, gid=gid)

    # check if there are permissions
    resolved_access_rights = await _get_resolved_access_rights(
        connection,
        folder_id,
        gid,
        permissions=permissions,
        enforece_all_permissions=enforece_all_permissions,
    )
    if resolved_access_rights is None:
        raise InsufficientPermissionsError(
            folder_id=folder_id,
            gid=gid,
            permissions=_only_true_permissions(permissions),
        )

    return resolved_access_rights


###
### API DB LAYER
###


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
    parse_obj_as(FolderName, name)

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
            # .where(folders_access_rights.c.gid == gid)
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
                    **OWNER_PERMISSIONS.to_dict(),
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
            **sharing_permissions.to_dict(),
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
        _BasePermissions.UPDATE_FOLDER
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
            folders_access_rights.select().where(
                folders_access_rights.c.traversal_parent_id == folder_id
            )
        )
        rows = await results.fetchall()
        if rows:
            for entry in rows:
                childern_folder_ids.append(entry.folder_id)  # noqa: PERF401

    # first remove all childeren
    for child_folder_id in childern_folder_ids:
        await folder_delete(connection, child_folder_id, gid)

    # as a last step remove the folder per se
    async with connection.begin():
        await connection.execute(folders.delete().where(folders.c.id == folder_id))


async def folder_move(
    connection: SAConnection,
    source_folder_id: _FolderID,
    gid: _GroupID,
    *,
    destination_folder_id: _FolderID | None,
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

        source_access_gid = source_access_entry.gid
        group_type: GroupType | None = await connection.scalar(
            sa.select([groups.c.type]).where(groups.c.gid == source_access_gid)
        )
        if group_type is None or group_type != GroupType.PRIMARY:
            raise CannotMoveFolderSharedViaNonPrimaryGroupError(
                group_type=group_type, gid=source_access_gid
            )
        if destination_folder_id:
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
    project_uuid: _ProjectID,
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
                .where(folders_to_projects.c.project_uuid == project_uuid)
            )
        ).fetchone()
        if project_in_folder_entry:
            raise ProjectAlreadyExistsInFolderError(
                project_uuid=project_uuid, folder_id=folder_id
            )

        # finally add project to folder
        await connection.execute(
            folders_to_projects.insert().values(
                folder_id=folder_id, project_uuid=project_uuid
            )
        )


async def folder_remove_project(
    connection: SAConnection,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    project_uuid: _ProjectID,
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
            .where(folders_to_projects.c.project_uuid == project_uuid)
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
            resolved_access_rights = await _check_folder_and_access(
                connection,
                folder_id=folder_id,
                gid=gid,
                permissions=required_permissions,
                enforece_all_permissions=False,
            )
            access_via_gid = resolved_access_rights.gid
            access_via_folder_id = resolved_access_rights.folder_id

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
                folders_access_rights.c.created.label("selected_created"),
                folders_access_rights.c.modified.label("selected_modified"),
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
