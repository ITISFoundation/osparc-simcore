import datetime
import uuid
from typing import Any

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .errors import ForeignKeyViolation
from .models.projects import projects
from .models.projects_metadata import projects_metadata

#
# Errors
#


class DBProjectNotFoundError(Exception):
    ...


#
# Data
#


class ProjectMetadata(BaseModel):
    custom: dict[str, Any] | None
    created: datetime.datetime | None
    modified: datetime.datetime | None
    parent_project_uuid: uuid.UUID | None
    parent_node_id: uuid.UUID | None

    class Config:
        frozen = True
        orm_mode = True


#
# Helpers
#


async def get(connection: SAConnection, project_uuid: uuid.UUID) -> ProjectMetadata:
    # JOIN LEFT OUTER
    get_stmt = (
        sa.select(
            projects.c.uuid,
            projects_metadata.c.custom,
            projects_metadata.c.created,
            projects_metadata.c.modified,
            projects_metadata.c.parent_project_uuid,
            projects_metadata.c.parent_node_id,
        )
        .select_from(
            sa.join(
                projects,
                projects_metadata,
                projects.c.uuid == projects_metadata.c.project_uuid,
                isouter=True,
            )
        )
        .where(projects.c.uuid == f"{project_uuid}")
    )
    result: ResultProxy = await connection.execute(get_stmt)
    row: RowProxy | None = await result.first()
    if row is None:
        msg = f"Project project_uuid={project_uuid!r} not found"
        raise DBProjectNotFoundError(msg)
    return ProjectMetadata.from_orm(row)


async def upsert(
    connection: SAConnection,
    *,
    project_uuid: uuid.UUID,
    custom_metadata: dict[str, Any],
    parent_project_uuid: uuid.UUID | None,
    parent_node_id: uuid.UUID | None,
) -> ProjectMetadata:
    data = {
        "project_uuid": f"{project_uuid}",
        "custom": custom_metadata,
        "parent_projet_uuid": (
            f"{parent_project_uuid}" if parent_project_uuid is not None else None
        ),
        "parent_node_id": f"{parent_node_id}" if parent_node_id is not None else None,
    }
    insert_stmt = pg_insert(projects_metadata).values(**data)
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[projects_metadata.c.project_uuid],
        set_=data,
    ).returning(sa.literal_column("*"))

    try:
        result: ResultProxy = await connection.execute(upsert_stmt)
        row: RowProxy | None = await result.first()
        assert row  # nosec
        return ProjectMetadata.from_orm(row)

    except ForeignKeyViolation as err:
        raise DBProjectNotFoundError(project_uuid) from err
