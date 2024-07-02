import datetime
import re
import uuid
from typing import Any, Final, TypeAlias, TypedDict

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from psycopg2.errors import ForeignKeyViolation
from pydantic import BaseModel, NonNegativeInt, PositiveInt
from pydantic.errors import PydanticErrorMixin
from simcore_postgres_database.models.folders import (
    folders,
    folders_access_rights,
    folders_to_projects,
)
from sqlalchemy.dialects import postgresql

_ProjectID: TypeAlias = uuid.UUID
_GroupID: TypeAlias = PositiveInt
_FolderID: TypeAlias = PositiveInt


class ORMModeBaseModel(BaseModel):
    class Config:
        frozen = True
        orm_mode = True
        allow_population_by_field_name = True


class FolderEntry(ORMModeBaseModel):
    folder_id: _FolderID
    name: str
    owner: _GroupID
    gid: _GroupID
    parent_folder: _FolderID | None

    read: bool
    write: bool
    delete: bool
    admin: bool

    created_at: datetime.datetime
    last_modified: datetime.datetime


class ProjectInFolderEntry(ORMModeBaseModel):
    folder_id: _FolderID
    project_id: _ProjectID
    owner: _GroupID

    created_at: datetime.datetime
    last_modified: datetime.datetime


class FoldersError(PydanticErrorMixin, RuntimeError):
    pass


class GroupIdDoesNotExistError(FoldersError):
    msg_template = "Provided group id '{gid}' does not exist "


class CouldNotCreateFolderError(FoldersError):
    msg_template = "Could not create folder='{folder}' and parent='{parent}'"


class FolderAlreadyExistsError(FoldersError):
    msg_template = (
        "A folder='{folder}' with parent='{parent}' for group='{gid}' already exists"
    )


class ParentFolderIsNotWritableError(FoldersError):
    msg_template = "Cannot create any sub-folders inside folder_id={parent_folder_id} since it is not writable for gid={gid}."


class BasePermissionError(FoldersError):
    pass


class CannotAlterOwnerPermissionsError(BasePermissionError):
    msg_template = (
        "Cannot change permission for the owner (gid={gid}) of folder_id={folder_id}!"
    )


class CannotGrantPermissionError(BasePermissionError):
    msg_template = (
        "folder_id={folder_id} might not exit or it was not shared with any of "
        "your groups groups ({gids}) with the following permissions: {permissions}"
    )


class RequiresOwnerToMakeAdminError(BasePermissionError):
    msg_template = "Only owner can share folder with 'admin' rights. No owner found in gids={gids} for folder_id={folder_id}"


class NoAccessToFolderFoundrError(BasePermissionError):
    msg_template = "could not find an entry for folder_id={folder_id} and gid={gid}"


class NoWriteAccessToFolderError(BasePermissionError):
    msg_template = "folder folder_id={folder_id} owned by gid={gid} has no write access"


class CannotRenameFolderError(BasePermissionError):
    msg_template = "no folder folder_id={folder_id} owned by any of gids={gids} has 'admin' permission"


class ProjectRemovalAccessRightsEntryNotFoundError(BasePermissionError):
    msg_template = "no folder_id={folder_id} found for gid={gid}"


class ProjectRemovalRequiresDeleteAccessError(BasePermissionError):
    msg_template = "could not remove project_id={project_id}, missing 'delete' permission for folder_id={folder_id} and gid={gid}"


class MissingProjectFolderError(FoldersError):
    msg_template = (
        "Could not find an folder for folder_id={folder_id} and project_id={project_id}"
    )


class CouldNotFindFolderError(FoldersError):
    msg_template = "Could not find an entry for folder_id={folder_id}, gid={gid}"


class ProjectAlreadyExistsInFolderError(FoldersError):
    msg_template = "could not add project for gid={gid}. Project project_id={project_id} in folder folder_id={folder_id} is already owned by owner={owner}"


class CouldNotDeleteMissingAccessError(FoldersError):
    msg_template = "No delete permission found for folder_id={folder_id}, gid={gid}"


class InvalidFolderNameError(FoldersError):
    msg_template = "Provided folder name='{name}' is invalid: {reason}"


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


class _PermissionsType(TypedDict):
    read: bool
    write: bool
    delete: bool
    admin: bool


def _parse_permissions(
    *, read: bool, write: bool, delete: bool, admin: bool = False
) -> _PermissionsType:
    # ensure admin always has all the permissions
    return (
        {"read": True, "write": True, "delete": True, "admin": True}
        if admin
        else {"read": read, "write": write, "delete": delete, "admin": False}
    )


async def folder_create(
    connection: SAConnection,
    name: str,
    gid: _GroupID,
    *,
    parent: _FolderID | None = None,
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
            .where(folders_access_rights.c.read.is_(True))
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
                .where(folders_access_rights.c.write.is_(True))
            )
            if not has_write_access_in_parent:
                raise ParentFolderIsNotWritableError(parent_folder_id=parent, gid=gid)

        # folder entry can now be inserted
        try:
            folder_id = await connection.scalar(
                sa.insert(folders).values(name=name, owner=gid).returning(folders.c.id)
            )

            if not folder_id:
                raise CouldNotCreateFolderError(folder=name, parent=parent)

            await connection.execute(
                sa.insert(folders_access_rights).values(
                    folder_id=folder_id,
                    gid=gid,
                    parent_folder=parent,
                    # NOTE the gid that owns the folder always has full permissions
                    **_parse_permissions(
                        read=True, write=True, delete=True, admin=True
                    ),
                )
            )
        except ForeignKeyViolation as e:
            raise GroupIdDoesNotExistError(gid=gid) from e

        return _FolderID(folder_id)


async def folder_share(
    connection: SAConnection,
    folder_id: _FolderID,
    sharing_gids: set[_GroupID],
    *,
    recipient_gid: _GroupID,
    parent_folder: _FolderID | None = None,
    recipient_read: bool = False,
    recipient_write: bool = False,
    recipient_delete: bool = False,
    recipient_admin: bool = False,
) -> None:
    # Permission change rules:
    # - `owner`` can never loose any permission, always has all of them
    # - `admin` can edit and remove permissions of every other user, including other `admins`
    # - `admin` is granted only by the owner

    async with connection.begin():
        # check that owner permissions are never alterd not even by the owner itself
        query_possible_owner_entry = await (
            await connection.execute(
                sa.select([folders, folders_access_rights])
                .select_from(
                    folders.join(
                        folders_access_rights,
                        folders.c.id == folders_access_rights.c.folder_id,
                    )
                )
                .where(folders_access_rights.c.gid == recipient_gid)
            )
        ).fetchone()
        if query_possible_owner_entry:
            owner_entry = FolderEntry.from_orm(query_possible_owner_entry)
            if owner_entry.owner == owner_entry.gid:
                raise CannotAlterOwnerPermissionsError(
                    gid=recipient_gid, folder_id=folder_id
                )

        if recipient_admin:
            query_can_grant_admin = (
                sa.select([folders, folders_access_rights])
                .select_from(
                    folders.join(
                        folders_access_rights,
                        folders.c.id == folders_access_rights.c.folder_id,
                    )
                )
                .where(folders_access_rights.c.folder_id == folder_id)
                .where(folders_access_rights.c.gid.in_(sharing_gids))
                .where(folders_access_rights.c.gid == folders.c.owner)
                .where(folders_access_rights.c.admin.is_(True))
            )
            can_grant_admin = await connection.scalar(query_can_grant_admin)
            if not can_grant_admin:
                raise RequiresOwnerToMakeAdminError(
                    folder_id=folder_id, gids=sharing_gids
                )

        # check if any of the sharing groups have the required requested permissions
        def _get_permissions_query(column: sa.Column) -> sa.sql.Select:
            # NOTE: permissions can be granted if that group has the admin permission
            # set and it also has access to the permission
            return (
                sa.select([folders_access_rights.c.folder_id])
                .where(folders_access_rights.c.folder_id == folder_id)
                .where(folders_access_rights.c.gid.in_(sharing_gids))
                .where(folders_access_rights.c.admin.is_(True))
                .where(column.is_(True))
            )

        if recipient_read:
            has_read_permision = await connection.scalar(
                _get_permissions_query(folders_access_rights.c.read)
            )
            if not has_read_permision:
                raise CannotGrantPermissionError(
                    folder_id=folder_id,
                    gids=sharing_gids,
                    permissions={"read", "admin"},
                )
        if recipient_write:
            has_write_permision = await connection.scalar(
                _get_permissions_query(folders_access_rights.c.write)
            )
            if not has_write_permision:
                raise CannotGrantPermissionError(
                    folder_id=folder_id,
                    gids=sharing_gids,
                    permissions={"write", "admin"},
                )
        if recipient_delete:
            has_delete_permision = await connection.scalar(
                _get_permissions_query(folders_access_rights.c.delete)
            )
            if not has_delete_permision:
                raise CannotGrantPermissionError(
                    folder_id=folder_id,
                    gids=sharing_gids,
                    permissions={"delete", "admin"},
                )

        # when setting all permissions to False admin rights are still required
        has_admin_permission_or_exists = await connection.scalar(
            sa.select([folders_access_rights.c.folder_id])
            .where(folders_access_rights.c.folder_id == folder_id)
            .where(folders_access_rights.c.gid.in_(sharing_gids))
            .where(folders_access_rights.c.admin.is_(True))
        )
        if not has_admin_permission_or_exists:
            raise CannotGrantPermissionError(
                folder_id=folder_id, gids=sharing_gids, permissions={"admin"}
            )

        # update or create permissions
        data: dict[str, Any] = {
            "folder_id": folder_id,
            "gid": recipient_gid,
            "parent_folder": parent_folder,
            **_parse_permissions(
                read=recipient_read,
                write=recipient_write,
                delete=recipient_delete,
                admin=recipient_admin,
            ),
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


async def folder_rename(
    connection: SAConnection, folder_id: _FolderID, gids: set[_GroupID], *, name: str
) -> None:
    # admin users only can rename the folder, all other users are not allowed
    async with connection.begin():
        valid_folder_id: int | None = await connection.scalar(
            sa.select([folders.c.id])
            .select_from(
                folders.join(
                    folders_access_rights,
                    folders.c.id == folders_access_rights.c.folder_id,
                )
            )
            .where(folders.c.id == folder_id)
            .where(folders_access_rights.c.gid.in_(gids))
            .where(folders_access_rights.c.admin.is_(True))
        )
        if not valid_folder_id:
            raise CannotRenameFolderError(folder_id=folder_id, gids=gids)

        # use this to change it
        await connection.execute(
            folders.update().where(folders.c.id == valid_folder_id).values(name=name)
        )


async def folder_delete(
    connection: SAConnection, folder_id: _FolderID, gid: _GroupID
) -> None:
    # NOTE when deleting a folder it only removes children that are owned by
    # `gid`. If they are owned by a different user they will be skipped.
    # This is the more conservative route and will not upset users

    own_children: list[_FolderID] = []

    async with connection.begin():
        found_entry: RowProxy | None = await (
            await connection.execute(
                sa.select([folders, folders_access_rights])
                .select_from(
                    folders.join(
                        folders_access_rights,
                        folders.c.id == folders_access_rights.c.folder_id,
                    )
                )
                .where(folders.c.id == folder_id)
                .where(folders_access_rights.c.gid == gid)
            )
        ).fetchone()

        if found_entry is None:
            raise CouldNotFindFolderError(folder_id=folder_id, gid=gid)
        folder_entry = FolderEntry.from_orm(found_entry)

        if not folder_entry.delete:
            raise CouldNotDeleteMissingAccessError(folder_id=folder_id, gid=gid)

        # list all children then delete
        results = await connection.execute(
            folders_access_rights.select()
            .where(folders_access_rights.c.parent_folder == folder_id)
            .where(folders_access_rights.c.gid == gid)
        )
        rows = await results.fetchall()
        if rows:
            for entry in rows:
                own_children.append(entry.folder_id)  # noqa: PERF401

        # NOTE: first access rights are removed
        # and lastly if it's the owner the folder entry is also removed
        await connection.execute(
            folders_access_rights.delete()
            .where(folders_access_rights.c.folder_id == folder_id)
            .where(folders_access_rights.c.gid == gid)
        )
        if folder_entry.owner == folder_entry.gid:
            await connection.execute(folders.delete().where(folders.c.id == folder_id))

    # finally remove all the children from the folder
    for child_folder_id in own_children:
        await folder_delete(connection, child_folder_id, gid)


async def folder_move(
    connection: SAConnection,
    folder_id: _FolderID,
    gids: set[_GroupID],
    *,
    new_parent_id: _FolderID,
) -> None:
    # TODO: make sure parent is not self
    # TODO: enforce access rights
    pass


async def folder_list(
    # maybe this one should be private and we need a more generic listing
    # TODO: think about how this will be used and add it based on that!
    connection: SAConnection,
    gids: set[_GroupID],
    *,
    parent_folder: _FolderID | None = None,
) -> list[_FolderID]:
    # TODO: with pagination
    return []


async def folder_add_project(
    connection: SAConnection,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    project_id: _ProjectID,
) -> None:
    async with connection.begin():
        # check access rights from folder
        access_rights = await (
            await connection.execute(
                folders_access_rights.select()
                .where(folders_access_rights.c.folder_id == folder_id)
                .where(folders_access_rights.c.gid == gid)
            )
        ).fetchone()
        if not access_rights:
            raise NoAccessToFolderFoundrError(gid=gid, folder_id=folder_id)

        if not access_rights.write:
            raise NoWriteAccessToFolderError(gid=gid, folder_id=folder_id)

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
                project_id=project_id,
                owner=project_in_folder_entry.owner,
                gid=gid,
                folder_id=folder_id,
            )

        # finally add project to folder
        await connection.execute(
            folders_to_projects.insert().values(
                folder_id=folder_id, project_id=project_id, owner=gid
            )
        )


async def folder_remove_project(
    connection: SAConnection,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    project_id: _ProjectID,
) -> None:
    # project is removed from folder only if the gid has permisisons on said folder
    async with connection.begin():
        entry_exists = await (
            await connection.execute(
                folders_to_projects.select()
                .where(folders_to_projects.c.folder_id == folder_id)
                .where(folders_to_projects.c.project_id == project_id)
            )
        ).fetchone()
        if not entry_exists:
            raise MissingProjectFolderError(project_id=project_id, folder_id=folder_id)

        # ensure has permissions to remove the folder
        folder_access_entry = await (
            await connection.execute(
                folders_access_rights.select()
                .where(folders_access_rights.c.folder_id == folder_id)
                .where(folders_access_rights.c.gid == gid)
            )
        ).fetchone()
        if not folder_access_entry:
            raise ProjectRemovalAccessRightsEntryNotFoundError(
                folder_id=folder_id, gid=gid
            )

        if not folder_access_entry.delete:
            raise ProjectRemovalRequiresDeleteAccessError(
                project_id=project_id, folder_id=folder_id, gid=gid
            )

        await connection.execute(
            folders_to_projects.delete()
            .where(folders_to_projects.c.folder_id == folder_id)
            .where(folders_to_projects.c.project_id == project_id)
        )


async def folder_list_projects(
    # TODO: -> maybe this one should be merged with the Other function that simply lists the root element?
    # or maybe this one could be private
    connection: SAConnection,
    folder_id: _FolderID,
    gids: set[_GroupID],
) -> list[_ProjectID]:
    # TODO: with pagination
    return []
