""" Database API

    - Adds a layer to the postgres API with a focus on the projects comments

"""

import logging
from datetime import datetime
from typing import Final

from aiohttp import web
from models_library.folders import FolderID
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import BaseModel
from simcore_postgres_database.models.projects_to_folders import projects_to_folders
from simcore_postgres_database.utils_repos import transaction_context
from simcore_service_webserver.utils import UnSet, as_dict_exclude_unset
from sqlalchemy import func, literal_column
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import select

from ..db.plugin import get_asyncpg_engine, get_database_engine

_logger = logging.getLogger(__name__)

_unset: Final = UnSet()

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


### AsyncPg


async def update_project_to_folder(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    folders_id_or_ids: FolderID | set[FolderID],
    filter_by_user_id: UserID | None | UnSet = _unset,
    # updatable columns
    user_id: UserID | None | UnSet = _unset,
) -> None:
    """
    Batch/single patch of project to folders
    """
    # NOTE: exclude unset can also be done using a pydantic model and dict(exclude_unset=True)
    updated = as_dict_exclude_unset(
        user_id=user_id,
    )

    query = projects_to_folders.update().values(modified=func.now(), **updated)

    if isinstance(folders_id_or_ids, set):
        # batch-update
        query = query.where(
            projects_to_folders.c.folder_id.in_(list(folders_id_or_ids))
        )
    else:
        # single-update
        query = query.where(projects_to_folders.c.folder_id == folders_id_or_ids)

    if not isinstance(filter_by_user_id, UnSet):
        query = query.where(projects_to_folders.c.user_id == filter_by_user_id)

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.stream(query)


async def delete_all_project_to_folder_by_project_ids_not_in_folder_ids(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id_or_ids: ProjectID | set[ProjectID],
    # Optional filter
    not_in_folder_ids: set[FolderID],
) -> None:
    query = projects_to_folders.delete()

    if isinstance(project_id_or_ids, set):
        # batch-delete
        query = query.where(
            projects_to_folders.c.project_uuid.in_(list(project_id_or_ids))
        )
    else:
        # single-delete
        query = query.where(
            projects_to_folders.c.project_uuid == f"{project_id_or_ids}"
        )

    query = query.where(
        projects_to_folders.c.folder_id.not_in(  # <-- NOT IN!
            [f"{folder_id}" for folder_id in not_in_folder_ids]
        )
    )

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.stream(query)
