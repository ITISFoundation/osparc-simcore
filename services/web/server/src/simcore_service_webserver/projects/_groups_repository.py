import logging

from aiohttp import web
from models_library.groups import GroupID
from models_library.projects import ProjectID
from pydantic import TypeAdapter
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy import func, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import select

from ..db.plugin import get_asyncpg_engine
from ._groups_models import ProjectGroupGetDB
from .exceptions import ProjectGroupNotFoundError

_logger = logging.getLogger(__name__)


async def create_project_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
) -> ProjectGroupGetDB:
    query = (
        project_to_groups.insert()
        .values(
            project_uuid=f"{project_id}",
            gid=group_id,
            read=read,
            write=write,
            delete=delete,
            created=func.now(),
            modified=func.now(),
        )
        .returning(literal_column("*"))
    )

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(query)
        row = await result.first()
        return ProjectGroupGetDB.model_validate(row)


async def list_project_groups(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
) -> list[ProjectGroupGetDB]:
    stmt = (
        select(
            project_to_groups.c.gid,
            project_to_groups.c.read,
            project_to_groups.c.write,
            project_to_groups.c.delete,
            project_to_groups.c.created,
            project_to_groups.c.modified,
        )
        .select_from(project_to_groups)
        .where(project_to_groups.c.project_uuid == f"{project_id}")
    )

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(stmt)
        rows = await result.all() or []
        return TypeAdapter(list[ProjectGroupGetDB]).validate_python(rows)


async def get_project_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    group_id: GroupID,
) -> ProjectGroupGetDB:
    stmt = (
        select(
            project_to_groups.c.gid,
            project_to_groups.c.read,
            project_to_groups.c.write,
            project_to_groups.c.delete,
            project_to_groups.c.created,
            project_to_groups.c.modified,
        )
        .select_from(project_to_groups)
        .where(
            (project_to_groups.c.project_uuid == f"{project_id}")
            & (project_to_groups.c.gid == group_id)
        )
    )

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(stmt)
        row = await result.first()
        if row is None:
            raise ProjectGroupNotFoundError(
                details=f"Project {project_id} group {group_id} not found"
            )
        return ProjectGroupGetDB.model_validate(row)


async def replace_project_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
) -> ProjectGroupGetDB:

    query = (
        project_to_groups.update()
        .values(
            read=read,
            write=write,
            delete=delete,
        )
        .where(
            (project_to_groups.c.project_uuid == f"{project_id}")
            & (project_to_groups.c.gid == group_id)
        )
        .returning(literal_column("*"))
    )

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(query)
        row = await result.first()
        if row is None:
            raise ProjectGroupNotFoundError(
                details=f"Project {project_id} group {group_id} not found"
            )
        return ProjectGroupGetDB.model_validate(row)


async def update_or_insert_project_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        insert_stmt = pg_insert(project_to_groups).values(
            project_uuid=f"{project_id}",
            gid=group_id,
            read=read,
            write=write,
            delete=delete,
            created=func.now(),
            modified=func.now(),
        )
        on_update_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[project_to_groups.c.project_uuid, project_to_groups.c.gid],
            set_={
                "read": insert_stmt.excluded.read,
                "write": insert_stmt.excluded.write,
                "delete": insert_stmt.excluded.delete,
                "modified": func.now(),
            },
        )
        await conn.stream(on_update_stmt)


async def delete_project_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    group_id: GroupID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.stream(
            project_to_groups.delete().where(
                (project_to_groups.c.project_uuid == f"{project_id}")
                & (project_to_groups.c.gid == group_id)
            )
        )


async def delete_all_project_groups(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.stream(
            project_to_groups.delete().where(
                project_to_groups.c.project_uuid == f"{project_id}"
            )
        )
