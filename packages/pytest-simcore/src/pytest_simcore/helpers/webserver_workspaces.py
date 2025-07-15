import sqlalchemy as sa
from aiohttp import web
from models_library.groups import GroupID
from models_library.workspaces import WorkspaceID
from simcore_postgres_database.models.workspaces_access_rights import (
    workspaces_access_rights,
)
from simcore_service_webserver.db.plugin import get_database_engine_legacy
from sqlalchemy.dialects.postgresql import insert as pg_insert


async def update_or_insert_workspace_group(
    app: web.Application,
    workspace_id: WorkspaceID,
    group_id: GroupID,
    *,
    read: bool,
    write: bool,
    delete: bool,
) -> None:
    async with get_database_engine_legacy(app).acquire() as conn:
        insert_stmt = pg_insert(workspaces_access_rights).values(
            workspace_id=workspace_id,
            gid=group_id,
            read=read,
            write=write,
            delete=delete,
            created=sa.func.now(),
            modified=sa.func.now(),
        )
        on_update_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[
                workspaces_access_rights.c.workspace_id,
                workspaces_access_rights.c.gid,
            ],
            set_={
                "read": insert_stmt.excluded.read,
                "write": insert_stmt.excluded.write,
                "delete": insert_stmt.excluded.delete,
                "modified": sa.func.now(),
            },
        )
        await conn.execute(on_update_stmt)
