import uuid
from typing import TypeAlias

import psycopg2
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from pydantic import PositiveInt
from pydantic.errors import PydanticErrorMixin
from simcore_postgres_database.models.folders import folders, folders_access_rights

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


class CouldNotFindFolderError(FoldersError):
    msg_template = (
        "Could not find an entry for folder_id {folder_id} and group_ids={group_ids}"
    )


class CouldNotDeleteMissingWriteAccessError(FoldersError):
    msg_template = "No write permission found for entry folder_id={folder_id} using group_ids={group_ids}"


def _get_query_check_existing_folder(
    name: str, gid: _GroupID, parent: _FolderID | None = None
) -> sa.sql.Select:
    return (
        sa.select([folders.c.id])
        .select_from(
            folders.join(
                folders_access_rights,
                folders.c.id == folders_access_rights.c.folder_id,
            )
        )
        .where(folders.c.name == name)
        .where(folders_access_rights.c.gid == gid)
        .where(folders.c.parent_folder == parent)
    )


async def folders_create(
    connection: SAConnection,
    name: str,
    gid: _GroupID,
    *,
    parent: _FolderID | None = None,
    read: bool = True,
    write: bool = True,
    delete: bool = True,
) -> _FolderID:
    async with connection.begin():
        existing_folder_id: int | None = await connection.scalar(
            _get_query_check_existing_folder(name, gid, parent)
        )
        if existing_folder_id:
            raise FolderAlreadyExistsError(folder=name, parent=parent, gid=gid)

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


async def folders_delete(
    connection: SAConnection, folder_id: _FolderID, group_ids: set[_GroupID]
) -> None:
    # NOTE on emulating linux
    # the owner of a folder can delete files and directories from another user
    search_query = (
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
    async with connection.begin():
        query_result: ResultProxy = await connection.execute(search_query)
        row_entry: RowProxy | None = await query_result.fetchone()

        if row_entry is None:
            raise CouldNotFindFolderError(folder_id=folder_id, group_ids=group_ids)

        if not row_entry.delete:
            raise CouldNotDeleteMissingWriteAccessError(
                folder_id=folder_id, group_ids=group_ids
            )

        # remove entries form both tables
        await connection.execute(folders.delete().where(folders.c.id == folder_id))


async def folders_move(
    connection: SAConnection,
    folder_id: _FolderID,
    new_parent_id: _FolderID,
    group_ids: set[_GroupID],
) -> None:
    # TODO: make sure parent is not self
    pass


async def folders_share(
    connection: SAConnection,
    folder_id: _FolderID,
    shared_group_ids: set[_GroupID],
    recipient_group_id: _GroupID,
) -> None:
    pass


async def folders_list(
    # TODO: think about how this will be used and add it based on that!
    connection: SAConnection,
    folder_id: _FolderID,
    group_ids: set[_GroupID],
) -> list[_FolderID]:
    pass


async def folders_to_projects_add(
    connection: SAConnection, project_id: _ProjectID, folder_id: _FolderID
) -> None:
    pass


async def folders_to_projects_remove(
    connection: SAConnection,
    project_id: _ProjectID,
    folder_id: _FolderID,
    group_ids: set[_GroupID],
) -> None:
    pass


async def folders_to_projects_move(
    connection: SAConnection,
    project_id: _ProjectID,
    current_folder_id: _FolderID,
    new_folder_id: _FolderID,
    group_ids: set[_GroupID],
) -> None:
    pass


async def folders_to_projects_list(
    connection: SAConnection,
    project_id: _ProjectID,
    folder_id: _FolderID,
    group_ids: set[_GroupID],
) -> list[_ProjectID]:
    pass
