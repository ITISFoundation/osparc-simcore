import logging

import sqlalchemy as sa
from aiohttp import web
from models_library.projects import ProjectID, ProjectIDStr
from pydantic import HttpUrl, TypeAdapter
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.models.projects import ProjectType, projects
from typing_extensions import (  # https://docs.pydantic.dev/latest/api/standard_library_types/#typeddict
    TypedDict,
)

from ..db.plugin import get_database_engine
from ..projects.api import ProjectPermalink, register_permalink_factory
from ..projects.exceptions import PermalinkNotAllowedError, ProjectNotFoundError
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
    """Checks criteria and defines how a permalink is built

    Raises:
        PermalinkNotAllowedError if some criteria are not fulfilled
    """

    # check: criterias/conditions on a project to have a permalink
    if project_type != ProjectType.TEMPLATE:
        raise PermalinkNotAllowedError(
            "Can only create permalink from a template project. "
            f"Got {project_uuid=} with {project_type=}"
        )

    project_access_rights_group_1_or_empty: _GroupAccessRightsDict | dict = (
        project_access_rights.get("1", {})
    )
    if not project_access_rights_group_1_or_empty.get("read", False):
        raise PermalinkNotAllowedError(
            "Cannot create permalink if not shared with everyone. "
            f"Got {project_uuid=} with {project_access_rights=}"
        )

    # create
    url_for = create_url_for_function(request)
    permalink = TypeAdapter(HttpUrl).validate_python(
        url_for(route_name="get_redirection_to_study_page", id=f"{project_uuid}"),
    )

    return ProjectPermalink(
        url=permalink,
        is_public=project_is_public,
    )


async def permalink_factory(
    request: web.Request, project_uuid: ProjectID
) -> ProjectPermalink:
    """
    - Assumes project_id is up-to-date in the database

    """
    # NOTE: next iterations will mobe this as part of the project repository pattern
    engine = get_database_engine(request.app)
    async with engine.acquire() as conn:
        access_rights_subquery = (
            sa.select(
                project_to_groups.c.project_uuid,
                sa.func.jsonb_object_agg(
                    project_to_groups.c.gid,
                    sa.func.jsonb_build_object(
                        "read",
                        project_to_groups.c.read,
                        "write",
                        project_to_groups.c.write,
                        "delete",
                        project_to_groups.c.delete,
                    ),
                ).label("access_rights"),
            )
            .where(project_to_groups.c.project_uuid == f"{project_uuid}")
            .group_by(project_to_groups.c.project_uuid)
        ).subquery("access_rights_subquery")

        stmt = (
            sa.select(
                projects.c.uuid,
                projects.c.type,
                access_rights_subquery.c.access_rights,
                projects.c.published,
            )
            .select_from(projects.join(access_rights_subquery, isouter=True))
            .where(projects.c.uuid == f"{project_uuid}")
        )
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
