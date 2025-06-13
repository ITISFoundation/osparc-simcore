"""Utils to implement READ operations (from cRud) on the project resource


Read operations are list, get

"""

from collections.abc import Coroutine
from typing import Any

from aiohttp import web
from models_library.folders import FolderID, FolderQuery, FolderScope
from models_library.projects import ProjectID, ProjectTemplateType
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.workspaces import WorkspaceID, WorkspaceQuery, WorkspaceScope
from pydantic import NonNegativeInt
from servicelib.utils import logged_gather
from simcore_postgres_database.models.projects import ProjectType
from simcore_postgres_database.webserver_models import (
    ProjectTemplateType as ProjectTemplateTypeDB,
)
from simcore_postgres_database.webserver_models import ProjectType as ProjectTypeDB
from simcore_service_webserver.users.api import get_user_email_legacy

from ..folders import _folders_repository
from ..workspaces.api import check_user_workspace_access
from . import _projects_service
from ._access_rights_repository import batch_get_project_access_rights
from ._projects_repository import batch_get_trashed_by_primary_gid
from ._projects_repository_legacy import ProjectDBAPI, convert_to_schema_names
from .models import ProjectDict, ProjectTypeAPI


def _batch_update(
    key: str,
    value_per_object: list[Any],
    objects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    for obj, value in zip(objects, value_per_object, strict=True):
        obj[key] = value
    return objects


async def _paralell_update(*update_per_object: Coroutine) -> list[Any]:
    return await logged_gather(
        *update_per_object,
        reraise=True,
        max_concurrency=100,
    )


async def _aggregate_data_to_projects_from_other_sources(
    app: web.Application,
    *,
    db_projects: list[ProjectDict],
    user_id: UserID,
) -> list[ProjectDict]:
    """
    Aggregates data to each project from other sources, first as a batch-update and then as a parallel-update.
    """
    # updating `project.trashed_by_primary_gid`
    trashed_by_primary_gid_values = await batch_get_trashed_by_primary_gid(
        app, projects_uuids=[ProjectID(p["uuid"]) for p in db_projects]
    )

    _batch_update("trashed_by_primary_gid", trashed_by_primary_gid_values, db_projects)

    # Add here get batch Project access rights
    project_to_access_rights = await batch_get_project_access_rights(
        app=app,
        projects_uuids_with_workspace_id=[
            (ProjectID(p["uuid"]), p["workspaceId"]) for p in db_projects
        ],
    )

    # udpating `project.state`
    update_state_per_project = [
        _projects_service.add_project_states_for_user(
            user_id=user_id,
            project=prj,
            is_template=prj["type"] == ProjectTypeDB.TEMPLATE,
            app=app,
        )
        for prj in db_projects
    ]

    updated_projects: list[ProjectDict] = await _paralell_update(
        *update_state_per_project,
    )

    for project in updated_projects:
        project["accessRights"] = project_to_access_rights[project["uuid"]]

    return updated_projects


async def _convert_db_projects_to_api_projects(
    app: web.Application,
    db,
    db_projects: list,
) -> list[dict]:
    """
    Converts db schema projects to API schema (legacy postprocessing).
    """
    api_projects: list[dict] = []
    for db_prj in db_projects:
        db_prj_dict = db_prj.model_dump()
        db_prj_dict.pop("product_name", None)
        db_prj_dict["tags"] = await db.get_tags_by_project(project_id=f"{db_prj.id}")
        user_email = await get_user_email_legacy(app, db_prj.prj_owner)
        api_projects.append(convert_to_schema_names(db_prj_dict, user_email))
    return api_projects


async def list_projects(  # pylint: disable=too-many-arguments
    app: web.Application,
    user_id: UserID,
    product_name: str,
    *,
    # hierachy filter
    workspace_id: WorkspaceID | None,
    folder_id: FolderID | None,
    # attrs filter
    project_type: ProjectTypeAPI,
    template_type: ProjectTemplateType | None,
    show_hidden: bool,  # NOTE: Be careful, this filters only hidden projects
    trashed: bool | None,
    # search
    search_by_multi_columns: str | None = None,
    search_by_project_name: str | None = None,
    # pagination
    offset: NonNegativeInt,
    limit: int,
    # ordering
    order_by: OrderBy,
) -> tuple[list[ProjectDict], int]:
    db = ProjectDBAPI.get_from_app_context(app)

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
        await _folders_repository.get_for_user_or_workspace(
            app,
            folder_id=folder_id,
            product_name=product_name,
            user_id=user_id if workspace_is_private else None,
            workspace_id=workspace_id,
        )

    db_projects, total_number_projects = await db.list_projects_dicts(
        product_name=product_name,
        user_id=user_id,
        workspace_query=(
            WorkspaceQuery(
                workspace_scope=WorkspaceScope.SHARED, workspace_id=workspace_id
            )
            if workspace_id
            else WorkspaceQuery(workspace_scope=WorkspaceScope.PRIVATE)
        ),
        folder_query=(
            FolderQuery(folder_scope=FolderScope.SPECIFIC, folder_id=folder_id)
            if folder_id
            else FolderQuery(folder_scope=FolderScope.ROOT)
        ),
        # attrs
        filter_by_project_type=ProjectTypeAPI.to_project_type_db(project_type),
        filter_by_template_type=(
            ProjectTemplateTypeDB(template_type) if template_type else None
        ),
        filter_trashed=trashed,
        filter_hidden=show_hidden,
        # composed attrs
        search_by_multi_columns=search_by_multi_columns,
        search_by_project_name=search_by_project_name,
        # pagination
        offset=offset,
        limit=limit,
        # order
        order_by=order_by,
    )

    api_projects = await _convert_db_projects_to_api_projects(app, db, db_projects)

    final_projects = await _aggregate_data_to_projects_from_other_sources(
        app, db_projects=api_projects, user_id=user_id
    )

    return final_projects, total_number_projects


async def list_projects_full_depth(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: str,
    # attrs filter
    trashed: bool | None,
    # pagination
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
    # search
    search_by_multi_columns: str | None,
    search_by_project_name: str | None,
) -> tuple[list[ProjectDict], int]:
    db = ProjectDBAPI.get_from_app_context(app)

    db_projects, total_number_projects = await db.list_projects_dicts(
        product_name=product_name,
        user_id=user_id,
        workspace_query=WorkspaceQuery(workspace_scope=WorkspaceScope.ALL),
        folder_query=FolderQuery(folder_scope=FolderScope.ALL),
        filter_trashed=trashed,
        filter_by_project_type=ProjectType.STANDARD,
        search_by_multi_columns=search_by_multi_columns,
        search_by_project_name=search_by_project_name,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )

    api_projects = await _convert_db_projects_to_api_projects(app, db, db_projects)

    final_projects = await _aggregate_data_to_projects_from_other_sources(
        app, db_projects=api_projects, user_id=user_id
    )

    return final_projects, total_number_projects
