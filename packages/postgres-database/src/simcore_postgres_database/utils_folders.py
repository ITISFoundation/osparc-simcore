import re
import uuid
from typing import Any, Final, TypeAlias

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from psycopg2.errors import ForeignKeyViolation
from pydantic import NonNegativeInt, PositiveInt
from pydantic.errors import PydanticErrorMixin
from simcore_postgres_database.models.folders import folders, folders_access_rights
from sqlalchemy.dialects.postgresql import insert

_ProjectID: TypeAlias = uuid.UUID
_GroupID: TypeAlias = PositiveInt
_FolderID: TypeAlias = PositiveInt


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


class ParentIsNotWritableError(FoldersError):
    msg_template = "Cannot create any sub-folders inside folder_id={parent_folder_id} since it is not writable for gid={gid}."


class SharingMissingPermissionsError(FoldersError):
    msg_template = "Cannot share folder_id={folder_id} owned by gids={gids} because parent does not have the following permissions: {permissions}"


class CouldNotFindFolderError(FoldersError):
    msg_template = (
        "Could not find an entry for folder_id {folder_id} and group_ids={group_ids}"
    )


class CouldNotDeleteMissingAccessError(FoldersError):
    msg_template = "No delete permission found for folder_id={folder_id} using group_ids={group_ids}"


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
            .where(folders.c.parent_folder == parent)
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
                raise ParentIsNotWritableError(parent_folder_id=parent, gid=gid)

        # folder entry can now be inserted
        try:
            folder_id = await connection.scalar(
                sa.insert(folders)
                .values(name=name, parent_folder=parent, created_by=gid)
                .returning(folders.c.id)
            )

            if not folder_id:
                raise CouldNotCreateFolderError(folder=name, parent=parent)

            await connection.execute(
                sa.insert(folders_access_rights).values(
                    folder_id=folder_id,
                    gid=gid,
                    # NOTE the gid that owns the folder always has full permissions
                    read=True,
                    write=True,
                    delete=True,
                )
            )
        except ForeignKeyViolation as e:
            raise GroupIdDoesNotExistError(gid=gid) from e

        return _FolderID(folder_id)


async def folder_share(
    connection: SAConnection,
    folder_id: _FolderID,
    shared_group_ids: set[_GroupID],
    *,
    recipient_group_id: _GroupID,
    recipient_read: bool = False,
    recipient_write: bool = False,
    recipient_delete: bool = False,
) -> None:
    """
    if any of the gids own the directory, folder can be shared
    # the permission must be given via the same permission level

    Arguments:
        connection -- _description_
        folder_id -- _description_
        shared_group_ids -- _description_
        recipient_group_id -- _description_

    Keyword Arguments:
        recipient_read -- _description_ (default: {_DEFAULT_ACCESS_READ})
        recipient_write -- _description_ (default: {_DEFAULT_ACCESS_WRITE})
        recipient_delete -- _description_ (default: {_DEFAULT_ACCESS_DELETE})
    """

    async with connection.begin():
        requested_permissions: dict["str", bool] = {}

        has_permissions_query = (
            sa.select([folders_access_rights.c.folder_id])
            .where(folders_access_rights.c.folder_id == folder_id)
            .where(folders_access_rights.c.gid.in_(shared_group_ids))
        )
        if recipient_read:
            has_permissions_query.where(
                folders_access_rights.c.read.is_(recipient_read)
            )
            requested_permissions["read"] = True
        if recipient_write:
            has_permissions_query.where(
                folders_access_rights.c.write.is_(recipient_write)
            )
            requested_permissions["write"] = True
        if recipient_delete:
            has_permissions_query.where(
                folders_access_rights.c.delete.is_(recipient_delete)
            )
            requested_permissions["delete"] = True

        has_permission: int | None = await connection.scalar(has_permissions_query)

        if not has_permission:
            raise SharingMissingPermissionsError(
                folder_id=folder_id,
                gids=shared_group_ids,
                permissions=requested_permissions,
            )

        # update or create permissions
        data: dict[str, Any] = {
            "folder_id": folder_id,
            "gid": recipient_group_id,
            "read": recipient_read,
            "write": recipient_write,
            "delete": recipient_delete,
        }
        insert_stmt = insert(folders_access_rights).values(**data)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[
                folders_access_rights.c.folder_id,
                folders_access_rights.c.gid,
            ],
            set_=data,
        )
        await connection.execute(upsert_stmt)


async def folder_delete(
    connection: SAConnection, folder_id: _FolderID, group_ids: set[_GroupID]
) -> None:
    # NOTE on emulating linux
    # the owner of a folder can delete files and directories from another user
    async with connection.begin():
        query_result: ResultProxy = await connection.execute(
            sa.select([folders, folders_access_rights])
            .select_from(
                folders.join(
                    folders_access_rights,
                    folders.c.id == folders_access_rights.c.folder_id,
                )
            )
            .where(folders.c.id == folder_id)
            .where(folders_access_rights.c.gid.in_(group_ids))
        )
        found_entry: RowProxy | None = None
        async for entry in query_result:
            if entry is not None:
                found_entry = entry

        if found_entry is None:
            raise CouldNotFindFolderError(folder_id=folder_id, group_ids=group_ids)

        if not found_entry.delete:
            raise CouldNotDeleteMissingAccessError(
                folder_id=folder_id, group_ids=group_ids
            )

        # this removes entry from folder_access_rights as well
        await connection.execute(folders.delete().where(folders.c.id == folder_id))


async def folder_move(
    connection: SAConnection,
    folder_id: _FolderID,
    group_ids: set[_GroupID],
    *,
    new_parent_id: _FolderID,
) -> None:
    # TODO: make sure parent is not self
    pass


async def folder_list(
    # TODO: think about how this will be used and add it based on that!
    connection: SAConnection,
    group_ids: set[_GroupID],
    *,
    parent_folder: _FolderID | None = None,
) -> list[_FolderID]:
    pass


# TODO: figure out which of these is required


async def project_in_folder_add(
    connection: SAConnection, project_id: _ProjectID, folder_id: _FolderID
) -> None:
    pass


async def project_in_folder_remove(
    connection: SAConnection,
    project_id: _ProjectID,
    folder_id: _FolderID,
    group_ids: set[_GroupID],
) -> None:
    pass


async def project_in_folder_move(
    connection: SAConnection,
    project_id: _ProjectID,
    current_folder_id: _FolderID,
    new_folder_id: _FolderID,
    group_ids: set[_GroupID],
) -> None:
    pass


async def project_in_folder_list(
    connection: SAConnection,
    project_id: _ProjectID,
    folder_id: _FolderID,
    group_ids: set[_GroupID],
) -> list[_ProjectID]:
    pass
