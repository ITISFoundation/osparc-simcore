""" Database API

    - Adds a layer to the postgres API with a focus on the projects comments

"""
import logging

from aiopg.sa.result import ResultProxy
from models_library.projects import ProjectID
from models_library.projects_comments import CommentID, ProjectsCommentsDB
from models_library.users import UserID
from pydantic import TypeAdapter
from pydantic.types import PositiveInt
from simcore_postgres_database.models.projects_comments import projects_comments
from sqlalchemy import func, literal_column
from sqlalchemy.sql import select

_logger = logging.getLogger(__name__)


async def create_project_comment(
    conn, project_uuid: ProjectID, user_id: UserID, contents: str
) -> CommentID:
    project_comment_id: ResultProxy = await conn.execute(
        projects_comments.insert()
        .values(
            project_uuid=project_uuid,
            user_id=user_id,
            contents=contents,
            modified=func.now(),
        )
        .returning(projects_comments.c.comment_id)
    )
    result: tuple[PositiveInt] = await project_comment_id.first()
    return TypeAdapter(CommentID).validate_python(result[0])


async def list_project_comments(
    conn,
    project_uuid: ProjectID,
    offset: PositiveInt,
    limit: int,
) -> list[ProjectsCommentsDB]:
    result = []
    project_comment_result: ResultProxy = await conn.execute(
        projects_comments.select()
        .where(projects_comments.c.project_uuid == f"{project_uuid}")
        .order_by(projects_comments.c.created.asc())
        .offset(offset)
        .limit(limit)
    )
    result = [
        ProjectsCommentsDB.model_validate(row)
        for row in await project_comment_result.fetchall()
    ]
    return result


async def total_project_comments(
    conn,
    project_uuid: ProjectID,
) -> PositiveInt:
    project_comment_result: ResultProxy = await conn.execute(
        select(func.count())
        .select_from(projects_comments)
        .where(projects_comments.c.project_uuid == f"{project_uuid}")
    )
    result: tuple[PositiveInt] = await project_comment_result.first()
    return result[0]


async def update_project_comment(
    conn,
    comment_id: CommentID,
    project_uuid: ProjectID,
    contents: str,
) -> ProjectsCommentsDB:
    project_comment_result = await conn.execute(
        projects_comments.update()
        .values(
            project_uuid=project_uuid,
            contents=contents,
            modified=func.now(),
        )
        .where(projects_comments.c.comment_id == comment_id)
        .returning(literal_column("*"))
    )
    result = await project_comment_result.first()
    return ProjectsCommentsDB.model_validate(result)


async def delete_project_comment(conn, comment_id: CommentID) -> None:
    await conn.execute(
        projects_comments.delete().where(projects_comments.c.comment_id == comment_id)
    )


async def get_project_comment(conn, comment_id: CommentID) -> ProjectsCommentsDB:
    project_comment_result = await conn.execute(
        projects_comments.select().where(projects_comments.c.comment_id == comment_id)
    )
    result = await project_comment_result.first()
    return ProjectsCommentsDB.model_validate(result)
