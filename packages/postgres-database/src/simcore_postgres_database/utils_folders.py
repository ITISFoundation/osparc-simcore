import re
import uuid
from typing import Final, TypeAlias

import psycopg2
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from pydantic import NonNegativeInt, PositiveInt
from pydantic.errors import PydanticErrorMixin
from simcore_postgres_database.models.folders import folders, folders_access_rights

_ProjectID: TypeAlias = uuid.UUID
_GroupID: TypeAlias = PositiveInt
_FolderID: TypeAlias = PositiveInt


_DEFAULT_ACCESS_READ: Final[bool] = True
_DEFAULT_ACCESS_WRITE: Final[bool] = False
_DEFAULT_ACCESS_DELETE: Final[bool] = False


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
    msg_template = "Cannot create any sub-folders inside folder_id={parent_folder_id} since it is not writable."


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
    read: bool = _DEFAULT_ACCESS_READ,
    write: bool = _DEFAULT_ACCESS_WRITE,
    delete: bool = _DEFAULT_ACCESS_DELETE,
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
                .where(folders_access_rights.c.write.is_(True))
            )
            if not has_write_access_in_parent:
                raise ParentIsNotWritableError(parent_folder_id=parent)

        # folder entry can now be inserted
        folder_id = await connection.scalar(
            sa.insert(folders)
            .values(name=name, parent_folder=parent)
            .returning(folders.c.id)
        )
        if not folder_id:
            raise CouldNotCreateFolderError(folder=name, parent=parent)

        try:
            await connection.execute(
                sa.insert(folders_access_rights).values(
                    folder_id=folder_id,
                    gid=gid,
                    read=read,
                    write=write,
                    delete=delete,
                )
            )
        except psycopg2.errors.ForeignKeyViolation as e:
            raise GroupIdDoesNotExistError(gid=gid) from e

        return _FolderID(folder_id)


async def folder_update_access(
    connection: SAConnection,
    folder_id: _FolderID,
    gid: _GroupID,
    *,
    new_read: bool | None = None,
    new_write: bool | None = None,
    new_delete: bool | None = None,
) -> None:
    values: dict[str, bool] = {}

    if new_read is not None:
        values["read"] = new_read
    if new_write is not None:
        values["write"] = new_write
    if new_delete is not None:
        values["delete"] = new_delete

    if not values:
        return

    await connection.execute(
        sa.update(folders_access_rights)
        .where(
            folders_access_rights.c.folder_id == folder_id,
            folders_access_rights.c.gid == gid,
        )
        .values(**values)
    )


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


async def folder_share(
    connection: SAConnection,
    folder_id: _FolderID,
    shared_group_ids: set[_GroupID],
    *,
    recipient_group_id: _GroupID,
) -> None:
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
