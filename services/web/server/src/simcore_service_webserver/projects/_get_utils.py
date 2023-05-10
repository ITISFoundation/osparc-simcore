from typing import Any

from aiohttp import web
from models_library.users import UserID
from pydantic import NonNegativeInt
from servicelib.utils import logged_gather
from simcore_postgres_database.webserver_models import ProjectType as ProjectTypeDB

from .. import catalog
from . import projects_api
from .project_models import ProjectTypeAPI
from .projects_db import ProjectDBAPI


async def _set_all_project_states(
    app: web.Application,
    user_id: UserID,
    projects: list[dict[str, Any]],
    project_types: list[ProjectTypeDB],
):
    await logged_gather(
        *[
            projects_api.add_project_states_for_user(
                user_id=user_id,
                project=prj,
                is_template=prj_type == ProjectTypeDB.TEMPLATE,
                app=app,
            )
            for prj, prj_type in zip(projects, project_types)
        ],
        reraise=True,
        max_concurrency=100,
    )


async def list_projects(
    request: web.Request,
    user_id: UserID,
    product_name: str,
    project_type: ProjectTypeAPI,
    show_hidden: bool,
    offset: NonNegativeInt,
    limit: int,
):

    app = request.app

    user_available_services: list[
        dict
    ] = await catalog.get_services_for_user_in_product(
        app, user_id, product_name, only_key_versions=True
    )

    db = ProjectDBAPI.get_from_app_context(app)

    projects, project_types, total_number_projects = await db.list_projects(
        user_id=user_id,
        product_name=product_name,
        filter_by_project_type=ProjectTypeAPI.to_project_type_db(project_type),
        filter_by_services=user_available_services,
        offset=offset,
        limit=limit,
        include_hidden=show_hidden,
    )
    await _set_all_project_states(
        app, user_id=user_id, projects=projects, project_types=project_types
    )

    return projects, total_number_projects
