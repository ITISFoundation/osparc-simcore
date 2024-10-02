import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import reduce
from typing import Annotated, Any, ClassVar, Final, TypeAlias, cast

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from models_library.errors_classes import OsparcErrorMixin
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    StringConstraints,
    TypeAdapter,
    ValidationError,
)
from simcore_postgres_database.utils_ordering import OrderByDict
from sqlalchemy import Column, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import BOOLEAN, INTEGER
from sqlalchemy.sql.elements import ColumnElement, Label
from sqlalchemy.sql.selectable import CTE

from .models.folders import folders, folders_access_rights, folders_to_projects
from .models.groups import GroupType, groups
from .utils_ordering import OrderDirection

_ProductName: TypeAlias = str
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
        * NoAccessForGroupsFoundError
    * BaseCreateFolderError
        * FolderAlreadyExistsError
        * ParentFolderIsNotWritableError
        * CouldNotCreateFolderError
        * GroupIdDoesNotExistError
        * RootFolderRequiresAtLeastOnePrimaryGroupError
    * BaseMoveFolderError
        * CannotMoveFolderSharedViaNonPrimaryGroupError
    * BaseAddProjectError
        * ProjectAlreadyExistsInFolderError
"""


class FoldersError(OsparcErrorMixin, RuntimeError):
    ...


class InvalidFolderNameError(FoldersError):
    msg_template = "Provided folder name='{name}' is invalid: {reason}"


class FolderAccessError(FoldersError):
    pass


class FolderNotFoundError(FolderAccessError):
    msg_template = "no entry found for folder_id={folder_id}, gids={gids} and product_name={product_name}"


class FolderNotSharedWithGidError(FolderAccessError):
    msg_template = "folder_id={folder_id} was not shared with gids={gids}"


class InsufficientPermissionsError(FolderAccessError):
    msg_template = "could not find a parent for folder_id={folder_id} and gids={gids}, with permissions={permissions}"


class NoAccessForGroupsFoundError(FolderAccessError):
    msg_template = "No parent found for folder_id={folder_id} and gids={gids}, with permissions={permissions}"


class BaseCreateFolderError(FoldersError):
    pass


class FolderAlreadyExistsError(BaseCreateFolderError):
    msg_template = "A folder='{folder}' with parent='{parent}' in product_name={product_name} already exists"


class ParentFolderIsNotWritableError(BaseCreateFolderError):
    msg_template = "Cannot create any sub-folders inside folder_id={parent_folder_id} since it is not writable for gid={gid}."


class CouldNotCreateFolderError(BaseCreateFolderError):
    msg_template = "Could not create folder='{folder}' and parent='{parent}'"


class NoGroupIDFoundError(BaseCreateFolderError):
    msg_template = "None of the provided gids='{gids}' was found"


class RootFolderRequiresAtLeastOnePrimaryGroupError(BaseCreateFolderError):
    msg_template = (
        "No parent={parent} defined and groupIDs={gids} did not contain a PRIMARY group. "
        "Cannot create a folder isnide the 'root' wihtout using the user's group."
    )


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
    GET_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(r=True)
    LIST_FOLDERS: ClassVar[_FolderPermissions] = _make_permissions(r=True)

    CREATE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(w=True)
    ADD_PROJECT_TO_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(w=True)

    SHARE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    UPDATE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    DELETE_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)
    REMOVE_PROJECT_FROM_FOLDER: ClassVar[_FolderPermissions] = _make_permissions(d=True)

    _MOVE_PROJECT_FROM_FOLDER_SOURCE: ClassVar[_FolderPermissions] = _make_permissions(
        d=True,
        description="apply to folder where the project is",
    )
    _MOVE_PROJECT_FROM_FOLDER_DESTINATION: ClassVar[
        _FolderPermissions
    ] = _make_permissions(
        w=True, description="apply on the folder receiving the project"
    )
    MOVE_PROJECT_FROM_FOLDER: ClassVar[_FolderPermissions] = _or_dicts_list(
        [_MOVE_PROJECT_FROM_FOLDER_SOURCE, _MOVE_PROJECT_FROM_FOLDER_DESTINATION]
    )

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


def _get_filter_for_enabled_permissions(
    permissions: _FolderPermissions, table: sa.Table | CTE
) -> ColumnElement | bool:
    clauses: list[ColumnElement] = []

    if permissions.read:
        clauses.append(table.c.read.is_(True))
    if permissions.write:
        clauses.append(table.c.write.is_(True))
    if permissions.delete:
        clauses.append(table.c.delete.is_(True))

    return sa.and_(*clauses) if clauses else True


###
### UTILS
###


FolderName: TypeAlias = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=255,
        pattern=re.compile(
            r'^(?!.*[<>:"/\\|?*\]])(?!.*\b(?:LPT9|COM1|LPT1|COM2|LPT3|LPT4|CON|COM5|COM3|COM4|AUX|PRN|LPT2|LPT5|COM6|LPT7|NUL|COM8|LPT6|COM9|COM7|LPT8)\b).+$',
            re.IGNORECASE,
        ),
    ),
]


class FolderEntry(BaseModel):
    id: _FolderID
    parent_folder: _FolderID | None = Field(alias="traversal_parent_id")
    name: str
    description: str
    owner: _GroupID = Field(alias="created_by")
    created: datetime = Field(alias="access_created")
    modified: datetime = Field(alias="access_modified")
    my_access_rights: _FolderPermissions
    access_rights: dict[_GroupID, _FolderPermissions]
    model_config = ConfigDict(from_attributes=True)


class _ResolvedAccessRights(BaseModel):
    folder_id: _FolderID
    gid: _GroupID
    traversal_parent_id: _FolderID | None
    original_parent_id: _FolderID | None
    read: bool
    write: bool
    delete: bool
    level: int
    model_config = ConfigDict(from_attributes=True)


async def _get_resolved_access_rights(
    connection: SAConnection,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    permissions: _FolderPermissions | None,
) -> _ResolvedAccessRights | None:

    # Define the anchor CTE
    access_rights_cte = (
        sa.select(
            folders_access_rights.c.folder_id,
            folders_access_rights.c.gid,
            folders_access_rights.c.traversal_parent_id,
            folders_access_rights.c.original_parent_id,
            folders_access_rights.c.read,
            folders_access_rights.c.write,
            folders_access_rights.c.delete,
            sa.literal_column("0").label("level"),
        )
        .where(folders_access_rights.c.folder_id == sa.bindparam("start_folder_id"))
        .cte(name="access_rights_cte", recursive=True)
    )

    # Define the recursive part of the CTE
    recursive = sa.select(
        folders_access_rights.c.folder_id,
        folders_access_rights.c.gid,
        folders_access_rights.c.traversal_parent_id,
        folders_access_rights.c.original_parent_id,
        folders_access_rights.c.read,
        folders_access_rights.c.write,
        folders_access_rights.c.delete,
        sa.literal_column("access_rights_cte.level + 1").label("level"),
    ).select_from(
        folders_access_rights.join(
            access_rights_cte,
            folders_access_rights.c.folder_id == access_rights_cte.c.original_parent_id,
        )
    )

    # Combine anchor and recursive CTE
    folder_hierarchy: CTE = access_rights_cte.union_all(recursive)

    # Final query to filter and order results
    query = (
        sa.select(
            folder_hierarchy.c.folder_id,
            folder_hierarchy.c.gid,
            folder_hierarchy.c.traversal_parent_id,
            folder_hierarchy.c.original_parent_id,
            folder_hierarchy.c.read,
            folder_hierarchy.c.write,
            folder_hierarchy.c.delete,
            folder_hierarchy.c.level,
        )
        .where(
            True
            if not permissions
            else _get_filter_for_enabled_permissions(permissions, folder_hierarchy)
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


async def _check_and_get_folder_access_by_group(
    connection: SAConnection,
    product_name: _ProductName,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    error_reporting_gids: set[_GroupID],
    permissions: _FolderPermissions,
) -> _ResolvedAccessRights:
    """
    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
    """
    folder_entry: int | None = await connection.scalar(
        sa.select(folders.c.id)
        .where(folders.c.id == folder_id)
        .where(folders.c.product_name == product_name)
    )
    if not folder_entry:
        raise FolderNotFoundError(
            folder_id=folder_id, gids=error_reporting_gids, product_name=product_name
        )

    # check if folder was shared
    resolved_access_rights_without_permissions = await _get_resolved_access_rights(
        connection,
        folder_id,
        gid,
        permissions=None,
    )
    if not resolved_access_rights_without_permissions:
        raise FolderNotSharedWithGidError(
            folder_id=folder_id, gids=error_reporting_gids
        )

    # check if there are permissions
    resolved_access_rights = await _get_resolved_access_rights(
        connection,
        folder_id,
        gid,
        permissions=permissions,
    )
    if resolved_access_rights is None:
        raise InsufficientPermissionsError(
            folder_id=folder_id,
            gids=error_reporting_gids,
            permissions=_only_true_permissions(permissions),
        )

    return resolved_access_rights


async def _check_and_get_folder_access(
    connection: SAConnection,
    product_name: _ProductName,
    folder_id: _FolderID,
    gids: set[_GroupID],
    *,
    permissions: _FolderPermissions,
) -> _ResolvedAccessRights:
    """
    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
        NoAccessForGroupsFoundError
    """
    folder_access_error = None

    for gid in gids:
        try:
            return await _check_and_get_folder_access_by_group(
                connection,
                product_name,
                folder_id,
                gid,
                error_reporting_gids=gids,
                permissions=permissions,
            )
        except FolderAccessError as e:  # noqa: PERF203
            folder_access_error = e

    if folder_access_error:
        raise folder_access_error

    raise NoAccessForGroupsFoundError(
        folder_id=folder_id,
        gids=gids,
        permissions=_only_true_permissions(permissions),
    )


###
### API DB LAYER
###


async def folder_create(
    connection: SAConnection,
    product_name: _ProductName,
    name: str,
    gids: set[_GroupID],
    description: str = "",
    parent: _FolderID | None = None,
    _required_permissions: _FolderPermissions = _requires(  # noqa: B008
        _BasePermissions.CREATE_FOLDER
    ),
) -> _FolderID:
    """
    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
        NoAccessForGroupsFoundError
        FolderAlreadyExistsError
        CouldNotCreateFolderError
        GroupIdDoesNotExistError
        RootFolderRequiresAtLeastOnePrimaryGroupError
    """
    try:
        TypeAdapter(FolderName).validate_python(name)
    except ValidationError as exc:
        raise InvalidFolderNameError(name=name, reason=f"{exc}") from exc

    async with connection.begin():
        entry_exists: int | None = await connection.scalar(
            sa.select(folders.c.id)
            .select_from(
                folders.join(
                    folders_access_rights,
                    folders.c.id == folders_access_rights.c.folder_id,
                )
            )
            .where(folders.c.name == name)
            .where(folders.c.product_name == product_name)
            .where(folders_access_rights.c.original_parent_id == parent)
        )
        if entry_exists:
            raise FolderAlreadyExistsError(
                product_name=product_name, folder=name, parent=parent
            )

        # `permissions_gid` is computed as follows:
        # - `folder has a parent?` taken from the resolved access rights of the parent folder
        # - `is root folder, a.k.a. no parent?` taken from the user's primary group
        permissions_gid = None
        if parent:
            resolved_access_rights = await _check_and_get_folder_access(
                connection,
                product_name,
                folder_id=parent,
                gids=gids,
                permissions=_required_permissions,
            )
            permissions_gid = resolved_access_rights.gid

        if permissions_gid is None:
            groups_results: list[RowProxy] | None = await (
                await connection.execute(
                    sa.select(groups.c.gid, groups.c.type).where(groups.c.gid.in_(gids))
                )
            ).fetchall()

            if not groups_results:
                raise NoGroupIDFoundError(gids=gids)

            primary_gid = None
            for group in groups_results:
                if group["type"] == GroupType.PRIMARY:
                    primary_gid = group["gid"]
            if primary_gid is None:
                raise RootFolderRequiresAtLeastOnePrimaryGroupError(
                    parent=parent, gids=gids
                )

            permissions_gid = primary_gid

        # folder entry can now be inserted
        folder_id = await connection.scalar(
            sa.insert(folders)
            .values(
                name=name,
                description=description,
                created_by=permissions_gid,
                product_name=product_name,
            )
            .returning(folders.c.id)
        )

        if not folder_id:
            raise CouldNotCreateFolderError(folder=name, parent=parent)

        await connection.execute(
            sa.insert(folders_access_rights).values(
                folder_id=folder_id,
                gid=permissions_gid,
                traversal_parent_id=parent,
                original_parent_id=parent,
                **OWNER_PERMISSIONS.to_dict(),
            )
        )

        return _FolderID(folder_id)


async def folder_share_or_update_permissions(
    connection: SAConnection,
    product_name: _ProductName,
    folder_id: _FolderID,
    sharing_gids: set[_GroupID],
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
        NoAccessForGroupsFoundError
    """
    # NOTE: if the `sharing_gid`` has permissions to share it can share it with any `FolderAccessRole`
    async with connection.begin():
        await _check_and_get_folder_access(
            connection,
            product_name,
            folder_id=folder_id,
            gids=sharing_gids,
            permissions=required_permissions,
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
    product_name: _ProductName,
    folder_id: _FolderID,
    gids: set[_GroupID],
    *,
    name: str | None = None,
    description: str | None = None,
    _required_permissions: _FolderPermissions = _requires(  # noqa: B008
        _BasePermissions.UPDATE_FOLDER
    ),
) -> None:
    """
    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
        NoAccessForGroupsFoundError
    """
    async with connection.begin():
        await _check_and_get_folder_access(
            connection,
            product_name,
            folder_id=folder_id,
            gids=gids,
            permissions=_required_permissions,
        )

        # do not update if nothing changed
        if name is None and description is None:
            return

        values: dict[str, str] = {}
        if name:
            values["name"] = name
        if description is not None:  # Can be empty string
            values["description"] = description

        # update entry
        await connection.execute(
            folders.update().where(folders.c.id == folder_id).values(**values)
        )


async def folder_delete(
    connection: SAConnection,
    product_name: _ProductName,
    folder_id: _FolderID,
    gids: set[_GroupID],
    *,
    _required_permissions: _FolderPermissions = _requires(  # noqa: B008
        _BasePermissions.DELETE_FOLDER
    ),
) -> None:
    """
    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
        NoAccessForGroupsFoundError
    """
    childern_folder_ids: list[_FolderID] = []

    async with connection.begin():
        await _check_and_get_folder_access(
            connection,
            product_name,
            folder_id=folder_id,
            gids=gids,
            permissions=_required_permissions,
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
        await folder_delete(connection, product_name, child_folder_id, gids)

    # as a last step remove the folder per se
    async with connection.begin():
        await connection.execute(folders.delete().where(folders.c.id == folder_id))


async def folder_move(
    connection: SAConnection,
    product_name: _ProductName,
    source_folder_id: _FolderID,
    gids: set[_GroupID],
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
        NoAccessForGroupsFoundError
        CannotMoveFolderSharedViaNonPrimaryGroupError:
    """
    async with connection.begin():
        source_access_entry = await _check_and_get_folder_access(
            connection,
            product_name,
            folder_id=source_folder_id,
            gids=gids,
            permissions=required_permissions_source,
        )

        source_access_gid = source_access_entry.gid
        group_type: GroupType | None = await connection.scalar(
            sa.select(groups.c.type).where(groups.c.gid == source_access_gid)
        )
        # Might drop primary check
        if group_type is None or group_type != GroupType.PRIMARY:
            raise CannotMoveFolderSharedViaNonPrimaryGroupError(
                group_type=group_type, gid=source_access_gid
            )
        if destination_folder_id:
            await _check_and_get_folder_access(
                connection,
                product_name,
                folder_id=destination_folder_id,
                gids=gids,
                permissions=required_permissions_destination,
            )

        # set new traversa_parent_id on the source_folder_id which is equal to destination_folder_id
        await connection.execute(
            folders_access_rights.update()
            .where(
                sa.and_(
                    folders_access_rights.c.folder_id == source_folder_id,
                    folders_access_rights.c.gid.in_(gids),
                )
            )
            .values(traversal_parent_id=destination_folder_id)
        )


async def folder_add_project(
    connection: SAConnection,
    product_name: _ProductName,
    folder_id: _FolderID,
    gids: set[_GroupID],
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
        NoAccessForGroupsFoundError
        ProjectAlreadyExistsInFolderError
    """
    async with connection.begin():
        await _check_and_get_folder_access(
            connection,
            product_name,
            folder_id=folder_id,
            gids=gids,
            permissions=required_permissions,
        )

        # check if already added in folder
        project_in_folder_entry = await (
            await connection.execute(
                folders_to_projects.select()
                .where(folders_to_projects.c.folder_id == folder_id)
                .where(folders_to_projects.c.project_uuid == f"{project_uuid}")
            )
        ).fetchone()
        if project_in_folder_entry:
            raise ProjectAlreadyExistsInFolderError(
                project_uuid=project_uuid, folder_id=folder_id
            )

        # finally add project to folder
        await connection.execute(
            folders_to_projects.insert().values(
                folder_id=folder_id, project_uuid=f"{project_uuid}"
            )
        )


async def folder_move_project(
    connection: SAConnection,
    product_name: _ProductName,
    source_folder_id: _FolderID,
    gids: set[_GroupID],
    *,
    project_uuid: _ProjectID,
    destination_folder_id: _FolderID | None,
    _required_permissions_source: _FolderPermissions = _requires(  # noqa: B008
        _BasePermissions._MOVE_PROJECT_FROM_FOLDER_SOURCE  # pylint:disable=protected-access # noqa: SLF001
    ),
    _required_permissions_destination: _FolderPermissions = _requires(  # noqa: B008
        _BasePermissions._MOVE_PROJECT_FROM_FOLDER_DESTINATION  # pylint:disable=protected-access # noqa: SLF001
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
        await _check_and_get_folder_access(
            connection,
            product_name,
            folder_id=source_folder_id,
            gids=gids,
            permissions=_required_permissions_source,
        )

    if destination_folder_id is None:
        # NOTE: As the project is moved to the root directory we will just remove it from the folders_to_projects table
        await folder_remove_project(
            connection,
            product_name,
            folder_id=source_folder_id,
            gids=gids,
            project_uuid=project_uuid,
        )
        return

    async with connection.begin():
        await _check_and_get_folder_access(
            connection,
            product_name,
            folder_id=destination_folder_id,
            gids=gids,
            permissions=_required_permissions_destination,
        )

        await connection.execute(
            folders_to_projects.delete()
            .where(folders_to_projects.c.folder_id == source_folder_id)
            .where(folders_to_projects.c.project_uuid == f"{project_uuid}")
        )
        await connection.execute(
            folders_to_projects.insert().values(
                folder_id=destination_folder_id, project_uuid=f"{project_uuid}"
            )
        )


async def get_project_folder_without_check(
    connection: SAConnection,
    *,
    project_uuid: _ProjectID,
) -> _FolderID | None:
    """
    This is temporary, until we discuss how to proceed. In first version we assume there is only one unique project uuid
    in the folders_to_projects table.

    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
        CannotMoveFolderSharedViaNonPrimaryGroupError:
    """
    async with connection.begin():
        folder_id = await connection.scalar(
            sa.select(folders_to_projects.c.folder_id).where(
                folders_to_projects.c.project_uuid == f"{project_uuid}"
            )
        )
        if folder_id:
            return _FolderID(folder_id)
        return None


async def folder_remove_project(
    connection: SAConnection,
    product_name: _ProductName,
    folder_id: _FolderID,
    gids: set[_GroupID],
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
        NoAccessForGroupsFoundError
    """
    async with connection.begin():
        await _check_and_get_folder_access(
            connection,
            product_name,
            folder_id=folder_id,
            gids=gids,
            permissions=required_permissions,
        )

        await connection.execute(
            folders_to_projects.delete()
            .where(folders_to_projects.c.folder_id == folder_id)
            .where(folders_to_projects.c.project_uuid == f"{project_uuid}")
        )


_LIST_GROUP_BY_FIELDS: Final[tuple[Column, ...]] = (
    folders.c.id,
    folders.c.name,
    folders.c.description,
    folders.c.created_by,
    folders_access_rights.c.traversal_parent_id,
)
_LIST_SELECT_FIELDS: Final[tuple[Label | Column, ...]] = (
    *_LIST_GROUP_BY_FIELDS,
    # access_rights
    (
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
    ).label("access_rights"),
    # my_access_rights
    func.json_build_object(
        "read",
        func.max(folders_access_rights.c.read.cast(INTEGER)).cast(BOOLEAN),
        "write",
        func.max(folders_access_rights.c.write.cast(INTEGER)).cast(BOOLEAN),
        "delete",
        func.max(folders_access_rights.c.delete.cast(INTEGER)).cast(BOOLEAN),
    ).label("my_access_rights"),
    # access_created
    func.max(folders_access_rights.c.created).label("access_created"),
    # access_modified
    func.max(folders_access_rights.c.modified).label("access_modified"),
)


async def folder_list(
    connection: SAConnection,
    product_name: _ProductName,
    folder_id: _FolderID | None,
    gids: set[_GroupID],
    *,
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    order_by: OrderByDict = OrderByDict(  # noqa: B008
        field="modified", direction=OrderDirection.DESC
    ),
    required_permissions: _FolderPermissions = _requires(  # noqa: B008
        _BasePermissions.LIST_FOLDERS
    ),
) -> tuple[int, list[FolderEntry]]:
    """
    Raises:
        FolderNotFoundError
        FolderNotSharedWithGidError
        InsufficientPermissionsError
        NoAccessForGroupsFoundError
    """
    # NOTE: when `folder_id is None` list the root folder of the `gids`

    if folder_id is not None:
        await _check_and_get_folder_access(
            connection,
            product_name,
            folder_id=folder_id,
            gids=gids,
            permissions=required_permissions,
        )

    results: list[FolderEntry] = []

    base_query = (
        sa.select(*_LIST_SELECT_FIELDS)
        .join(folders_access_rights, folders.c.id == folders_access_rights.c.folder_id)
        .where(folders.c.product_name == product_name)
        .where(
            folders_access_rights.c.traversal_parent_id.is_(None)
            if folder_id is None
            else folders_access_rights.c.traversal_parent_id == folder_id
        )
        .where(folders_access_rights.c.gid.in_(gids))
        .where(
            _get_filter_for_enabled_permissions(
                required_permissions, folders_access_rights
            )
        )
        .group_by(*_LIST_GROUP_BY_FIELDS)
    )

    # Select total count from base_query
    subquery = base_query.subquery()
    count_query = sa.select(sa.func.count()).select_from(subquery)
    count_result = await connection.execute(count_query)
    total_count = await count_result.scalar()

    # Ordering and pagination
    if order_by["direction"] == OrderDirection.ASC:
        list_query = base_query.order_by(sa.asc(getattr(folders.c, order_by["field"])))
    else:
        list_query = base_query.order_by(sa.desc(getattr(folders.c, order_by["field"])))
    list_query = list_query.offset(offset).limit(limit)

    async for entry in connection.execute(list_query):
        results.append(FolderEntry.from_orm(entry))  # noqa: PERF401s

    return cast(int, total_count), results


async def folder_get(
    connection: SAConnection,
    product_name: _ProductName,
    folder_id: _FolderID,
    gids: set[_GroupID],
    *,
    required_permissions: _FolderPermissions = _requires(  # noqa: B008
        _BasePermissions.GET_FOLDER
    ),
) -> FolderEntry:
    resolved_access_rights: _ResolvedAccessRights = await _check_and_get_folder_access(
        connection,
        product_name,
        folder_id=folder_id,
        gids=gids,
        permissions=required_permissions,
    )
    permissions_gid: _GroupID = resolved_access_rights.gid

    query = (
        sa.select(*_LIST_SELECT_FIELDS)
        .join(folders_access_rights, folders.c.id == folders_access_rights.c.folder_id)
        .where(folders_access_rights.c.folder_id == folder_id)
        .where(folders_access_rights.c.gid == permissions_gid)
        .where(
            _get_filter_for_enabled_permissions(
                required_permissions, folders_access_rights
            )
            if folder_id is None
            else True
        )
        .where(folders.c.product_name == product_name)
        .group_by(*_LIST_GROUP_BY_FIELDS)
    )

    query_result: RowProxy | None = await (await connection.execute(query)).fetchone()

    if query_result is None:
        raise FolderNotFoundError(
            folder_id=folder_id, gids=gids, product_name=product_name
        )

    return FolderEntry.from_orm(query_result)


__all__ = ["OrderByDict"]
