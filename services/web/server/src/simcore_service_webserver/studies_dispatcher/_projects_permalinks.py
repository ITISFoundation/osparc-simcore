import logging
from typing import TypedDict

import sqlalchemy as sa
from aiohttp import web
from models_library.projects import ProjectID, ProjectIDStr
from simcore_postgres_database.models.projects import ProjectType, projects
from simcore_service_webserver.projects.projects_exceptions import (
    PermalinkNotAllowedError,
    ProjectNotFoundError,
)
from yarl import URL

from ..db import get_database_engine
from ..projects.api import ProjectPermalink, register_permalink_factory
from ..utils_aiohttp import create_url_for_function
from .settings import StudiesDispatcherSettings

_logger = logging.getLogger(__name__)


# Expected inputs models
_GroupID = str


class _GroupAccessRightsDict(TypedDict):
    read: bool
    write: bool
    delete: bool


def create_permalink_for_study(
    request: web.Request,
    project_uuid: ProjectID | ProjectIDStr,
    project_type: ProjectType,
    project_access_rights: dict[_GroupID, _GroupAccessRightsDict],
    project_is_public: bool,
) -> ProjectPermalink:
    """

    Raises:
        PermalinkNotAllowedError
    """

    # checks
    if project_type != ProjectType.TEMPLATE:
        raise PermalinkNotAllowedError(
            "Can only create permalink from a template project. "
            f"Got {project_uuid=} with {project_type=}"
        )

    if not project_access_rights.get("1", {}).get("read", False):
        raise PermalinkNotAllowedError(
            "Cannot create permalink if not shared with everyone. "
            f"Got {project_uuid=} with {project_access_rights=}"
        )

    # create
    url_for = create_url_for_function(request)

    permalink: str = url_for(
        route_name="get_redirection_to_study_page", id=f"{project_uuid}"
    )

    return ProjectPermalink(
        url=f"{URL(permalink)}",
        is_public=project_is_public,
    )


assert "uuid" in projects.columns  # nosec
assert "type" in projects.columns  # nosec
assert "access_rights" in projects.columns  # nosec
assert "published" in projects.columns  # nosec


async def permalink_factory(
    request: web.Request, project_uuid: ProjectID
) -> ProjectPermalink:
    """
    - Assumes project_id is up-to-date in the database

    """
    engine = get_database_engine(request.app)
    # TODO: move to projects_utils?
    async with engine.acquire() as conn:
        stmt = sa.select(
            [
                projects.c.uuid,
                projects.c.type,
                projects.c.access_rights,
                projects.c.published,
            ]
        ).where(projects.c.uuid == f"{project_uuid}")
        result = await conn.execute(stmt)
        row = await result.first()
        if not row:
            raise ProjectNotFoundError(project_uuid=project_uuid)

    permalink_info = create_permalink_for_study(
        request,
        project_uuid=row.uuid,
        project_type=row.type,
        project_access_rights=row.access_rights,
        project_is_public=row.published,
    )
    return permalink_info


def setup_projects_permalinks(
    app: web.Application, settings: StudiesDispatcherSettings
):
    assert settings  # nosec
    register_permalink_factory(app, permalink_factory)
