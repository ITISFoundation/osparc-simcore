import datetime
from collections.abc import AsyncGenerator

import sqlalchemy as sa
from models_library.basic_types import SHA256Str
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from simcore_postgres_database.storage_models import file_meta_data
from sqlalchemy import and_, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from ...exceptions.errors import FileMetaDataNotFoundError
from ...models import FileMetaData, FileMetaDataAtDB, UserOrProjectFilter


async def exists(conn: AsyncConnection, file_id: SimcoreS3FileID) -> bool:
    return bool(
        await conn.scalar(
            sa.select(sa.func.count())
            .select_from(file_meta_data)
            .where(file_meta_data.c.file_id == file_id)
        )
        == 1
    )


async def upsert(
    conn: AsyncConnection, fmd: FileMetaData | FileMetaDataAtDB
) -> FileMetaDataAtDB:
    # NOTE: upsert file_meta_data, if the file already exists, we update the whole row
    # so we get the correct time stamps
    fmd_db = (
        FileMetaDataAtDB.model_validate(fmd) if isinstance(fmd, FileMetaData) else fmd
    )
    insert_statement = pg_insert(file_meta_data).values(**fmd_db.model_dump())
    on_update_statement = insert_statement.on_conflict_do_update(
        index_elements=[file_meta_data.c.file_id], set_=fmd_db.model_dump()
    ).returning(literal_column("*"))
    result = await conn.execute(on_update_statement)
    await conn.commit()
    row = result.one()
    assert row  # nosec
    return FileMetaDataAtDB.model_validate(row)


async def insert(conn: AsyncConnection, fmd: FileMetaData) -> FileMetaDataAtDB:
    fmd_db = FileMetaDataAtDB.model_validate(fmd)
    result = await conn.execute(
        file_meta_data.insert()
        .values(jsonable_encoder(fmd_db))
        .returning(literal_column("*"))
    )
    row = result.one()
    assert row  # nosec
    return FileMetaDataAtDB.model_validate(row)


async def get(conn: AsyncConnection, file_id: SimcoreS3FileID) -> FileMetaDataAtDB:
    result = await conn.execute(
        sa.select(file_meta_data).where(file_meta_data.c.file_id == file_id)
    )
    if row := result.first():
        return FileMetaDataAtDB.model_validate(row)
    raise FileMetaDataNotFoundError(file_id=file_id)


def _list_filter_with_partial_file_id_stmt(
    *,
    user_or_project_filter: UserOrProjectFilter,
    file_id_prefix: str | None,
    partial_file_id: str | None,
    sha256_checksum: SHA256Str | None,
    is_directory: bool | None,
    limit: int | None = None,
    offset: int | None = None,
):
    conditions: list = []

    # Checks access rights (project can be owned or shared)
    user_id = user_or_project_filter.user_id
    if user_id is not None:
        project_ids = user_or_project_filter.project_ids
        conditions.append(
            sa.or_(
                file_meta_data.c.user_id == f"{user_id}",
                (
                    file_meta_data.c.project_id.in_(f"{_}" for _ in project_ids)
                    if project_ids
                    else False
                ),
            )
        )

    # Optional filters
    if file_id_prefix:
        conditions.append(file_meta_data.c.file_id.startswith(file_id_prefix))
    if partial_file_id:
        conditions.append(file_meta_data.c.file_id.ilike(f"%{partial_file_id}%"))
    if is_directory is not None:
        conditions.append(file_meta_data.c.is_directory.is_(is_directory))
    if sha256_checksum:
        conditions.append(file_meta_data.c.sha256_checksum == sha256_checksum)

    return (
        sa.select(file_meta_data)
        .where(sa.and_(*conditions))
        .order_by(file_meta_data.c.created_at.asc())  # sorted as oldest first
        .offset(offset)
        .limit(limit)
    )


async def list_filter_with_partial_file_id(
    conn: AsyncConnection,
    *,
    user_or_project_filter: UserOrProjectFilter,
    file_id_prefix: str | None,
    partial_file_id: str | None,
    sha256_checksum: SHA256Str | None,
    is_directory: bool | None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[FileMetaDataAtDB]:
    stmt = _list_filter_with_partial_file_id_stmt(
        user_or_project_filter=user_or_project_filter,
        file_id_prefix=file_id_prefix,
        partial_file_id=partial_file_id,
        sha256_checksum=sha256_checksum,
        is_directory=is_directory,
        limit=limit,
        offset=offset,
    )

    return [
        FileMetaDataAtDB.model_validate(row) async for row in await conn.stream(stmt)
    ]


async def list_fmds(
    conn: AsyncConnection,
    *,
    user_id: UserID | None = None,
    project_ids: list[ProjectID] | None = None,
    file_ids: list[SimcoreS3FileID] | None = None,
    expired_after: datetime.datetime | None = None,
) -> list[FileMetaDataAtDB]:
    stmt = sa.select(file_meta_data).where(
        and_(
            (file_meta_data.c.user_id == f"{user_id}") if user_id else True,
            (
                (file_meta_data.c.project_id.in_([f"{p}" for p in project_ids]))
                if project_ids
                else True
            ),
            (file_meta_data.c.file_id.in_(file_ids)) if file_ids else True,
            (
                (file_meta_data.c.upload_expires_at < expired_after)
                if expired_after
                else True
            ),
        )
    )

    return [
        FileMetaDataAtDB.model_validate(row) async for row in await conn.stream(stmt)
    ]


async def total(conn: AsyncConnection) -> int:
    """returns the number of uploaded file entries"""
    return (
        await conn.scalar(sa.select(sa.func.count()).select_from(file_meta_data)) or 0
    )


async def list_valid_uploads(
    conn: AsyncConnection,
) -> AsyncGenerator[FileMetaDataAtDB, None]:
    """returns all the theoretically valid fmds (e.g. upload_expires_at column is null)"""
    async for row in await conn.stream(
        sa.select(file_meta_data).where(
            file_meta_data.c.upload_expires_at.is_(None)  # lgtm [py/test-equals-none]
        )
    ):
        fmd_at_db = FileMetaDataAtDB.model_validate(row)
        yield fmd_at_db


async def delete(conn: AsyncConnection, file_ids: list[SimcoreS3FileID]) -> None:
    await conn.execute(
        file_meta_data.delete().where(file_meta_data.c.file_id.in_(file_ids))
    )


async def delete_all_from_project(conn: AsyncConnection, project_id: ProjectID) -> None:
    await conn.execute(
        file_meta_data.delete().where(file_meta_data.c.project_id == f"{project_id}")
    )


async def delete_all_from_node(conn: AsyncConnection, node_id: NodeID) -> None:
    await conn.execute(
        file_meta_data.delete().where(file_meta_data.c.node_id == f"{node_id}")
    )
