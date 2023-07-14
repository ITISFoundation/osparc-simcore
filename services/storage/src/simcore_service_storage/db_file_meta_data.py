import datetime
from typing import AsyncGenerator

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import SimcoreS3FileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from simcore_postgres_database.storage_models import file_meta_data
from sqlalchemy import and_, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .exceptions import FileMetaDataNotFoundError
from .models import FileMetaData, FileMetaDataAtDB


async def exists(conn: SAConnection, file_id: SimcoreS3FileID) -> bool:
    return bool(
        await conn.scalar(
            sa.select(sa.func.count())
            .select_from(file_meta_data)
            .where(file_meta_data.c.file_id == file_id)
        )
        == 1
    )


async def upsert(
    conn: SAConnection, fmd: FileMetaData | FileMetaDataAtDB
) -> FileMetaDataAtDB:
    # NOTE: upsert file_meta_data, if the file already exists, we update the whole row
    # so we get the correct time stamps
    fmd_db = FileMetaDataAtDB.from_orm(fmd) if isinstance(fmd, FileMetaData) else fmd
    insert_statement = pg_insert(file_meta_data).values(**jsonable_encoder(fmd_db))
    on_update_statement = insert_statement.on_conflict_do_update(
        index_elements=[file_meta_data.c.file_id], set_=jsonable_encoder(fmd_db)
    ).returning(literal_column("*"))
    result = await conn.execute(on_update_statement)
    row = await result.first()
    assert row  # nosec
    return FileMetaDataAtDB.from_orm(row)


async def insert(conn: SAConnection, fmd: FileMetaData) -> FileMetaDataAtDB:
    fmd_db = FileMetaDataAtDB.from_orm(fmd)
    result = await conn.execute(
        file_meta_data.insert()
        .values(jsonable_encoder(fmd_db))
        .returning(literal_column("*"))
    )
    row = await result.first()
    assert row  # nosec
    return FileMetaDataAtDB.from_orm(row)


async def get(conn: SAConnection, file_id: SimcoreS3FileID) -> FileMetaDataAtDB:
    result = await conn.execute(
        query=sa.select(file_meta_data).where(file_meta_data.c.file_id == file_id)
    )
    if row := await result.first():
        return FileMetaDataAtDB.from_orm(row)
    raise FileMetaDataNotFoundError(file_id=file_id)


async def list_filter_with_partial_file_id(
    conn: SAConnection,
    *,
    user_id: UserID,
    project_ids: list[ProjectID],
    file_id_prefix: str | None,
    partial_file_id: str | None,
    only_files: bool,
) -> list[FileMetaDataAtDB]:
    stmt = sa.select(file_meta_data).where(
        (
            (file_meta_data.c.user_id == f"{user_id}")
            | file_meta_data.c.project_id.in_(f"{pid}" for pid in project_ids)
        )
        & (
            file_meta_data.c.file_id.startswith(file_id_prefix)
            if file_id_prefix
            else True
        )
        & (
            file_meta_data.c.file_id.ilike(f"%{partial_file_id}%")
            if partial_file_id
            else True
        )
        & (
            file_meta_data.c.is_directory.is_(False)  # noqa FBT003
            if only_files
            else True
        )
    )
    return [FileMetaDataAtDB.from_orm(row) async for row in await conn.execute(stmt)]


async def list_fmds(
    conn: SAConnection,
    *,
    user_id: UserID | None = None,
    project_ids: list[ProjectID] | None = None,
    file_ids: list[SimcoreS3FileID] | None = None,
    expired_after: datetime.datetime | None = None,
) -> list[FileMetaDataAtDB]:
    stmt = sa.select(file_meta_data).where(
        and_(
            (file_meta_data.c.user_id == f"{user_id}") if user_id else True,
            (file_meta_data.c.project_id.in_([f"{p}" for p in project_ids]))
            if project_ids
            else True,
            (file_meta_data.c.file_id.in_(file_ids)) if file_ids else True,
            (file_meta_data.c.upload_expires_at < expired_after)
            if expired_after
            else True,
        )
    )

    return [FileMetaDataAtDB.from_orm(row) async for row in await conn.execute(stmt)]


async def total(conn: SAConnection) -> int:
    """returns the number of uploaded file entries"""
    return (
        await conn.scalar(sa.select(sa.func.count()).select_from(file_meta_data)) or 0
    )


async def list_valid_uploads(
    conn: SAConnection,
) -> AsyncGenerator[FileMetaDataAtDB, None]:
    """returns all the theoretically valid fmds (e.g. upload_expires_at column is null)"""
    async for row in conn.execute(
        sa.select(file_meta_data).where(
            file_meta_data.c.upload_expires_at == None  # lgtm [py/test-equals-none]
        )
    ):
        fmd_at_db = FileMetaDataAtDB.from_orm(row)
        yield fmd_at_db


async def delete(conn: SAConnection, file_ids: list[SimcoreS3FileID]) -> None:
    await conn.execute(
        file_meta_data.delete().where(file_meta_data.c.file_id.in_(file_ids))
    )


async def delete_all_from_project(conn: SAConnection, project_id: ProjectID) -> None:
    await conn.execute(
        file_meta_data.delete().where(file_meta_data.c.project_id == f"{project_id}")
    )


async def delete_all_from_node(conn: SAConnection, node_id: NodeID) -> None:
    await conn.execute(
        file_meta_data.delete().where(file_meta_data.c.node_id == f"{node_id}")
    )
