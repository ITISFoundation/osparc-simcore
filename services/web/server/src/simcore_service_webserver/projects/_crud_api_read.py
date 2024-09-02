""" Utils to implement READ operations (from cRud) on the project resource


Read operations are list, get

"""

from aiohttp import web
from models_library.api_schemas_webserver._base import OutputSchema
from models_library.api_schemas_webserver.projects import ProjectListItem
from models_library.folders import FolderID
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.workspaces import WorkspaceID
from pydantic import NonNegativeInt
from servicelib.utils import logged_gather
from simcore_postgres_database.webserver_models import ProjectType as ProjectTypeDB
from simcore_service_webserver.workspaces._workspaces_api import (
    check_user_workspace_access,
)

from ..catalog.client import get_services_for_user_in_product
from ..folders import _folders_db as folders_db
from . import projects_api
from ._permalink_api import update_or_pop_permalink_in_project
from .db import ProjectDBAPI
from .models import ProjectDict, ProjectTypeAPI


async def _append_fields(
    request: web.Request,
    *,
    user_id: UserID,
    project: ProjectDict,
    is_template: bool,
    model_schema_cls: type[OutputSchema],
):
    # state
    await projects_api.add_project_states_for_user(
        user_id=user_id,
        project=project,
        is_template=is_template,
        app=request.app,
    )

    # permalink
    await update_or_pop_permalink_in_project(request, project)

    # validate
    return model_schema_cls.parse_obj(project).data(exclude_unset=True)


async def list_projects(  # pylint: disable=too-many-arguments
    request: web.Request,
    user_id: UserID,
    product_name: str,
    project_type: ProjectTypeAPI,
    show_hidden: bool,
    offset: NonNegativeInt,
    limit: int,
    search: str | None,
    order_by: OrderBy,
    folder_id: FolderID | None,
    workspace_id: WorkspaceID | None,
) -> tuple[list[ProjectDict], int]:
    app = request.app
    db = ProjectDBAPI.get_from_app_context(app)

    user_available_services: list[dict] = await get_services_for_user_in_product(
        app, user_id, product_name, only_key_versions=True
    )

    _personal_workspace_user_id_or_none: UserID | None = user_id
    if workspace_id:
        await check_user_workspace_access(
            app,
            user_id=user_id,
            workspace_id=workspace_id,
            product_name=product_name,
            permission="read",
        )
        _personal_workspace_user_id_or_none = None

    if folder_id:
        # Check whether user has access to the folder
        await folders_db.get_for_user_or_workspace(
            app,
            folder_id=folder_id,
            product_name=product_name,
            user_id=_personal_workspace_user_id_or_none,
            workspace_id=workspace_id,
        )

    db_projects, db_project_types, total_number_projects = await db.list_projects(
        personal_workspace_user_id_or_none=_personal_workspace_user_id_or_none,
        product_name=product_name,
        user_id=user_id,
        filter_by_project_type=ProjectTypeAPI.to_project_type_db(project_type),
        filter_by_services=user_available_services,
        offset=offset,
        limit=limit,
        include_hidden=show_hidden,
        search=search,
        order_by=order_by,
        folder_id=folder_id,
        workspace_id=workspace_id,
    )

    projects: list[ProjectDict] = await logged_gather(
        *(
            _append_fields(
                request,
                user_id=user_id,
                project=prj,
                is_template=prj_type == ProjectTypeDB.TEMPLATE,
                model_schema_cls=ProjectListItem,
            )
            for prj, prj_type in zip(db_projects, db_project_types)
        ),
        reraise=True,
        max_concurrency=100,
    )

    return projects, total_number_projects


async def get_project(
    request: web.Request,
    user_id: UserID,
    product_name: str,
    project_uuid: ProjectID,
    project_type: ProjectTypeAPI,
):
    raise NotImplementedError
