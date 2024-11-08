""" Utils to implement READ operations (from cRud) on the project resource


Read operations are list, get

"""

from aiohttp import web
from models_library.access_rights import AccessRights
from models_library.api_schemas_webserver._base import OutputSchema
from models_library.api_schemas_webserver.projects import ProjectListItem
from models_library.folders import FolderID
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy
from models_library.users import GroupID, UserID
from models_library.workspaces import WorkspaceID
from pydantic import NonNegativeInt
from servicelib.utils import logged_gather
from simcore_postgres_database.webserver_models import ProjectType as ProjectTypeDB
from simcore_service_webserver.workspaces._workspaces_api import (
    check_user_workspace_access,
)

from ..catalog.client import get_services_for_user_in_product
from ..folders import _folders_db as folders_db
from ..workspaces import _workspaces_db as workspaces_db
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
    workspace_access_rights: dict[GroupID, AccessRights] | None,
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

    # replace project access rights (if project is in workspace)
    if workspace_access_rights:
        project["accessRights"] = {
            gid: access.model_dump() for gid, access in workspace_access_rights.items()
        }

    # validate
    return model_schema_cls.model_validate(project).data(exclude_unset=True)


async def list_projects(  # pylint: disable=too-many-arguments
    request: web.Request,
    user_id: UserID,
    product_name: str,
    *,
    # hierachy filter
    workspace_id: WorkspaceID | None,
    folder_id: FolderID | None,
    # attrs filter
    project_type: ProjectTypeAPI,
    show_hidden: bool,
    trashed: bool | None,
    # pagination
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
    # search
    search: str | None,
) -> tuple[list[ProjectDict], int]:
    app = request.app
    db = ProjectDBAPI.get_from_app_context(app)

    user_available_services: list[dict] = await get_services_for_user_in_product(
        app, user_id, product_name, only_key_versions=True
    )

    workspace_is_private = True
    if workspace_id:
        await check_user_workspace_access(
            app,
            user_id=user_id,
            workspace_id=workspace_id,
            product_name=product_name,
            permission="read",
        )
        workspace_is_private = False

    if folder_id:
        # Check whether user has access to the folder
        await folders_db.get_for_user_or_workspace(
            app,
            folder_id=folder_id,
            product_name=product_name,
            user_id=user_id if workspace_is_private else None,
            workspace_id=workspace_id,
        )

    db_projects, db_project_types, total_number_projects = await db.list_projects(
        product_name=product_name,
        user_id=user_id,
        workspace_id=workspace_id,
        folder_id=folder_id,
        # attrs
        filter_by_project_type=ProjectTypeAPI.to_project_type_db(project_type),
        filter_by_services=user_available_services,
        trashed=trashed,
        hidden=show_hidden,
        # composed attrs
        search=search,
        # pagination
        offset=offset,
        limit=limit,
        # order
        order_by=order_by,
    )

    # If workspace, override project access rights
    workspace_access_rights = None
    if workspace_id:
        workspace_db = await workspaces_db.get_workspace_for_user(
            app, user_id=user_id, workspace_id=workspace_id, product_name=product_name
        )
        workspace_access_rights = workspace_db.access_rights

    projects: list[ProjectDict] = await logged_gather(
        *(
            _append_fields(
                request,
                user_id=user_id,
                project=prj,
                is_template=prj_type == ProjectTypeDB.TEMPLATE,
                workspace_access_rights=workspace_access_rights,
                model_schema_cls=ProjectListItem,
            )
            for prj, prj_type in zip(db_projects, db_project_types)
        ),
        reraise=True,
        max_concurrency=100,
    )

    return projects, total_number_projects


async def list_projects_full_search(
    request,
    *,
    user_id: UserID,
    product_name: str,
    offset: NonNegativeInt,
    limit: int,
    text: str | None,
    order_by: OrderBy,
    tag_ids_list: list[int],
) -> tuple[list[ProjectDict], int]:
    db = ProjectDBAPI.get_from_app_context(request.app)

    user_available_services: list[dict] = await get_services_for_user_in_product(
        request.app, user_id, product_name, only_key_versions=True
    )

    (
        db_projects,
        db_project_types,
        total_number_projects,
    ) = await db.list_projects_full_search(
        user_id=user_id,
        product_name=product_name,
        filter_by_services=user_available_services,
        text=text,
        offset=offset,
        limit=limit,
        order_by=order_by,
        tag_ids_list=tag_ids_list,
    )

    projects: list[ProjectDict] = await logged_gather(
        *(
            _append_fields(
                request,
                user_id=user_id,
                project=prj,
                is_template=prj_type == ProjectTypeDB.TEMPLATE,
                workspace_access_rights=None,
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
