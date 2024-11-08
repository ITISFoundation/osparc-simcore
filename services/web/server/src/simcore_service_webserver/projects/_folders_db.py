""" Database API

    - Adds a layer to the postgres API with a focus on the projects comments

"""

import logging
from datetime import datetime

from aiohttp import web
from models_library.folders import FolderID
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import BaseModel
from simcore_postgres_database.models.projects_to_folders import projects_to_folders
from sqlalchemy import func, literal_column
from sqlalchemy.sql import select

from ..db.plugin import get_database_engine

_logger = logging.getLogger(__name__)


_logger = logging.getLogger(__name__)

### Models


class ProjectToFolderDB(BaseModel):
    project_uuid: ProjectID
    folder_id: FolderID
    user_id: UserID | None
    created: datetime
    modified: datetime


## DB API


async def insert_project_to_folder(
    app: web.Application,
    project_id: ProjectID,
    folder_id: FolderID,
    private_workspace_user_id_or_none: UserID | None,
) -> ProjectToFolderDB:
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            projects_to_folders.insert()
            .values(
                project_uuid=f"{project_id}",
                folder_id=folder_id,
                user_id=private_workspace_user_id_or_none,
                created=func.now(),
                modified=func.now(),
            )
            .returning(literal_column("*"))
        )
        row = await result.first()
        return ProjectToFolderDB.model_validate(row)


async def get_project_to_folder(
    app: web.Application,
    *,
    project_id: ProjectID,
    private_workspace_user_id_or_none: UserID | None,
) -> ProjectToFolderDB | None:
    stmt = select(
        projects_to_folders.c.project_uuid,
        projects_to_folders.c.folder_id,
        projects_to_folders.c.user_id,
        projects_to_folders.c.created,
        projects_to_folders.c.modified,
    ).where(
        (projects_to_folders.c.project_uuid == f"{project_id}")
        & (projects_to_folders.c.user_id == private_workspace_user_id_or_none)
    )

    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(stmt)
        row = await result.first()
        if row is None:
            return None
        return ProjectToFolderDB.model_validate(row)


async def delete_project_to_folder(
    app: web.Application,
    project_id: ProjectID,
    folder_id: FolderID,
    private_workspace_user_id_or_none: UserID | None,
) -> None:
    async with get_database_engine(app).acquire() as conn:
        await conn.execute(
            projects_to_folders.delete().where(
                (projects_to_folders.c.project_uuid == f"{project_id}")
                & (projects_to_folders.c.folder_id == folder_id)
                & (projects_to_folders.c.user_id == private_workspace_user_id_or_none)
            )
        )


async def delete_all_project_to_folder_by_project_id(
    app: web.Application,
    project_id: ProjectID,
) -> None:
    async with get_database_engine(app).acquire() as conn:
        await conn.execute(
            projects_to_folders.delete().where(
                projects_to_folders.c.project_uuid == f"{project_id}"
            )
        )
