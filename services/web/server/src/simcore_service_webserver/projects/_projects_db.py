import logging

import sqlalchemy as sa
from aiohttp import web
from models_library.projects import ProjectID
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine
from .exceptions import ProjectNotFoundError
from .models import ProjectDB

_logger = logging.getLogger(__name__)


PROJECT_WITHOUT_WORKBENCH_COLS = [  # noqa: RUF012
    # NOTE: MD: I intentionally didn't include the workbench. There is a special interface
    # for the workbench, and at some point, this column should be removed from the table.
    # The same holds true for access_rights/ui/classifiers/quality, but we have decided to proceed step by step.
    projects.c.id,
    projects.c.type,
    projects.c.uuid,
    projects.c.name,
    projects.c.description,
    projects.c.thumbnail,
    projects.c.prj_owner,  # == user.id (who created)
    projects.c.creation_date,
    projects.c.last_change_date,
    projects.c.ui,
    projects.c.classifiers,
    projects.c.dev,
    projects.c.quality,
    projects.c.published,
    projects.c.hidden,
    projects.c.workspace_id,
    projects.c.trashed,
    projects.c.trashed_by,  # == user.id (who trashed)
    projects.c.trashed_explicitly,
]

BASE_PROJECT_SELECT_ARGS = [
    *PROJECT_WITHOUT_WORKBENCH_COLS,
    projects.c.workbench,
    users.c.primary_gid.label("trashed_by_primary_gid"),
    # NOTE: needs `.outerjoin(users, projects.c.trashed_by == users.c.id)`
]


async def patch_project(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_uuid: ProjectID,
    new_partial_project_data: dict,
) -> ProjectDB:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            projects.update()
            .values(last_change_date=sa.func.now(), **new_partial_project_data)
            .where(projects.c.uuid == f"{project_uuid}")
            .returning(*PROJECT_WITHOUT_WORKBENCH_COLS)
        )
        row = await result.first()
        if row is None:
            raise ProjectNotFoundError(project_uuid=project_uuid)
        return ProjectDB.model_validate(row)
