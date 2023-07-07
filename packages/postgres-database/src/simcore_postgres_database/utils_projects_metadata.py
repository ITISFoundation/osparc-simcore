import datetime
import uuid
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from simcore_postgres_database.models.projects_metadata import projects_metadata
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .errors import ForeignKeyViolation
from .models.projects import projects
from .utils_models import FromRowMixin

#
# Errors
#


class DBProjectNotFoundError(Exception):
    ...


#
# Data
#


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectMetadata(FromRowMixin):
    custom: dict[str, Any] | None
    created: datetime.datetime | None
    modified: datetime.datetime | None


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
    return ProjectMetadata.from_row(row)


async def upsert(
    connection: SAConnection,
    *,
    project_uuid: uuid.UUID,
    custom_metadata: dict[str, Any],
) -> ProjectMetadata:
    data = {
        "project_uuid": f"{project_uuid}",
        "custom": custom_metadata,
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
        return ProjectMetadata.from_row(row)

    except ForeignKeyViolation as err:
        raise DBProjectNotFoundError(project_uuid) from err
