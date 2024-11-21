import logging

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_comments import (
    CommentID,
    ProjectsCommentsAPI,
    ProjectsCommentsDB,
)
from models_library.users import UserID
from pydantic import PositiveInt

from .db import APP_PROJECT_DBAPI, ProjectDBAPI

log = logging.getLogger(__name__)


#
#  PROJECT COMMENTS -------------------------------------------------------------------
#


async def create_project_comment(
    request: web.Request, project_uuid: ProjectID, user_id: UserID, contents: str
) -> CommentID:
    db: ProjectDBAPI = request.app[APP_PROJECT_DBAPI]

    comment_id: CommentID = await db.create_project_comment(
        project_uuid, user_id, contents
    )
    return comment_id


async def list_project_comments(
    request: web.Request,
    project_uuid: ProjectID,
    offset: PositiveInt,
    limit: int,
) -> list[ProjectsCommentsAPI]:
    db: ProjectDBAPI = request.app[APP_PROJECT_DBAPI]

    projects_comments_db_model: list[
        ProjectsCommentsDB
    ] = await db.list_project_comments(project_uuid, offset, limit)
    projects_comments_api_model = [
        ProjectsCommentsAPI(**comment.model_dump())
        for comment in projects_comments_db_model
    ]
    return projects_comments_api_model


async def total_project_comments(
    request: web.Request,
    project_uuid: ProjectID,
) -> PositiveInt:
    db: ProjectDBAPI = request.app[APP_PROJECT_DBAPI]

    project_comments_total: PositiveInt = await db.total_project_comments(project_uuid)
    return project_comments_total


async def update_project_comment(
    request: web.Request,
    comment_id: CommentID,
    project_uuid: ProjectID,
    contents: str,
) -> ProjectsCommentsAPI:
    db: ProjectDBAPI = request.app[APP_PROJECT_DBAPI]

    projects_comments_db_model: ProjectsCommentsDB = await db.update_project_comment(
        comment_id, project_uuid, contents
    )
    projects_comments_api_model = ProjectsCommentsAPI(
        **projects_comments_db_model.model_dump()
    )
    return projects_comments_api_model


async def delete_project_comment(request: web.Request, comment_id: CommentID) -> None:
    db: ProjectDBAPI = request.app[APP_PROJECT_DBAPI]

    await db.delete_project_comment(comment_id)


async def get_project_comment(
    request: web.Request, comment_id: CommentID
) -> ProjectsCommentsAPI:
    db: ProjectDBAPI = request.app[APP_PROJECT_DBAPI]

    projects_comments_db_model: ProjectsCommentsDB = await db.get_project_comment(
        comment_id
    )
    projects_comments_api_model = ProjectsCommentsAPI(
        **projects_comments_db_model.model_dump()
    )
    return projects_comments_api_model
