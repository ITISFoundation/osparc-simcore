import datetime
from typing import AsyncGenerator, Optional

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import StorageFileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from simcore_postgres_database.models.file_meta_data import file_meta_data
from sqlalchemy import and_, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .exceptions import FileMetaDataNotFoundError
from .models import FileMetaData, FileMetaDataAtDB


def _convert_db_to_model(x: FileMetaDataAtDB) -> FileMetaData:
    return FileMetaData.parse_obj(
        x.dict()
        | {
            "file_uuid": x.file_id,
            "file_name": x.file_id.split("/")[-1],
        }
    )


async def fmd_exists(conn: SAConnection, file_id: StorageFileID) -> bool:
    return (
        await conn.scalar(
            sa.select([sa.func.count()])
            .select_from(file_meta_data)
            .where(file_meta_data.c.file_id == file_id)
        )
        == 1
    )


async def upsert_file_metadata_for_upload(
    conn: SAConnection, fmd: FileMetaData
) -> FileMetaData:
    # NOTE: upsert file_meta_data, if the file already exists, we update the whole row
    # so we get the correct time stamps
    fmd_db = FileMetaDataAtDB.from_orm(fmd)
    insert_statement = pg_insert(file_meta_data).values(**jsonable_encoder(fmd_db))
    on_update_statement = insert_statement.on_conflict_do_update(
        index_elements=[file_meta_data.c.file_id], set_=jsonable_encoder(fmd_db)
    )
    await conn.execute(on_update_statement)

    return fmd


async def insert_file_metadata(conn: SAConnection, fmd: FileMetaData) -> FileMetaData:
    fmd_db = FileMetaDataAtDB.from_orm(fmd)
    result = await conn.execute(
        file_meta_data.insert()
        .values(jsonable_encoder(fmd_db))
        .returning(literal_column("*"))
    )
    row = await result.first()
    assert row  # nosec
    return _convert_db_to_model(FileMetaDataAtDB.from_orm(row))


async def get(conn: SAConnection, file_id: StorageFileID) -> FileMetaData:
    result = await conn.execute(
        query=sa.select([file_meta_data]).where(file_meta_data.c.file_id == file_id)
    )
    if row := await result.fetchone():
        fmd_at_db = FileMetaDataAtDB.from_orm(row)
        return _convert_db_to_model(fmd_at_db)
    raise FileMetaDataNotFoundError(file_id=file_id)


async def list_fmds_with_partial_file_id(
    conn: SAConnection,
    *,
    user_id: UserID,
    project_ids: list[ProjectID],
    file_id_prefix: Optional[str],
    partial_file_id: Optional[str],
) -> list[FileMetaData]:
    stmt = sa.select([file_meta_data]).where(
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
    )
    file_metadatas = [
        _convert_db_to_model(FileMetaDataAtDB.from_orm(row))
        async for row in await conn.execute(stmt)
    ]
    return file_metadatas


async def list_fmds(
    conn: SAConnection,
    *,
    user_id: Optional[UserID] = None,
    project_ids: Optional[list[ProjectID]] = None,
    file_ids: Optional[list[StorageFileID]] = None,
    expired_after: Optional[datetime.datetime] = None,
) -> list[FileMetaData]:

    stmt = sa.select([file_meta_data]).where(
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

    file_metadatas = [
        _convert_db_to_model(FileMetaDataAtDB.from_orm(row))
        async for row in await conn.execute(stmt)
    ]
    return file_metadatas


async def number_of_uploaded_fmds(conn: SAConnection) -> int:
    """returns the number of uploaded file entries"""
    return (
        await conn.scalar(sa.select([sa.func.count()]).select_from(file_meta_data)) or 0
    )


async def list_all_uploaded_fmds(
    conn: SAConnection,
) -> AsyncGenerator[FileMetaData, None]:
    """returns all the theoretically valid fmds (e.g. upload_expires_at column is null)"""
    async for row in conn.execute(
        sa.select([file_meta_data]).where(file_meta_data.c.upload_expires_at == None)
    ):
        fmd_at_db = FileMetaDataAtDB.from_orm(row)
        yield _convert_db_to_model(fmd_at_db)


async def delete(conn: SAConnection, file_ids: list[StorageFileID]) -> None:
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
