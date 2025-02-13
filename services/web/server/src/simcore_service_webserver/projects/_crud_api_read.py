""" Utils to implement READ operations (from cRud) on the project resource


Read operations are list, get

"""

from typing import Any, Coroutine

from aiohttp import web
from models_library.folders import FolderID, FolderQuery, FolderScope
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.workspaces import WorkspaceID, WorkspaceQuery, WorkspaceScope
from pydantic import NonNegativeInt
from servicelib.utils import logged_gather
from simcore_postgres_database.models.projects import ProjectType
from simcore_postgres_database.webserver_models import ProjectType as ProjectTypeDB
from simcore_service_webserver.projects._permalink_api import (
    aggregate_permalink_in_project,
)
from simcore_service_webserver.projects._projects_db import (
    batch_get_trashed_by_primary_gid,
)

from ..catalog.client import get_services_for_user_in_product
from ..folders import _folders_repository as _folders_repository
from ..workspaces._workspaces_service import check_user_workspace_access
from . import projects_service
from .db import ProjectDBAPI
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
    db_project_types: list[ProjectTypeDB],
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

    # udpating `project.state`
    update_state_per_project = [
        projects_service.add_project_states_for_user(
            user_id=user_id,
            project=prj,
            is_template=prj_type == ProjectTypeDB.TEMPLATE,
            app=app,
        )
        for prj, prj_type in zip(db_projects, db_project_types, strict=False)
    ]

    updated_projects: list[ProjectDict] = await _paralell_update(
        *update_state_per_project,
    )

    return updated_projects


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
    show_hidden: bool,
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
        await _folders_repository.get_for_user_or_workspace(
            app,
            folder_id=folder_id,
            product_name=product_name,
            user_id=user_id if workspace_is_private else None,
            workspace_id=workspace_id,
        )

    db_projects, db_project_types, total_number_projects = await db.list_projects_dicts(
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
        filter_by_services=user_available_services,
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

    projects = await _aggregate_data_to_projects_from_other_sources(
        app, db_projects=db_projects, db_project_types=db_project_types, user_id=user_id
    )

    return projects, total_number_projects


async def list_projects_full_depth(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: str,
    # attrs filter
    trashed: bool | None,
    tag_ids_list: list[int],
    # pagination
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
    # search
    search_by_multi_columns: str | None,
    search_by_project_name: str | None,
) -> tuple[list[ProjectDict], int]:
    db = ProjectDBAPI.get_from_app_context(app)

    user_available_services: list[dict] = await get_services_for_user_in_product(
        app, user_id, product_name, only_key_versions=True
    )

    db_projects, db_project_types, total_number_projects = await db.list_projects_dicts(
        product_name=product_name,
        user_id=user_id,
        workspace_query=WorkspaceQuery(workspace_scope=WorkspaceScope.ALL),
        folder_query=FolderQuery(folder_scope=FolderScope.ALL),
        filter_trashed=trashed,
        filter_by_services=user_available_services,
        filter_tag_ids_list=tag_ids_list,
        filter_by_project_type=ProjectType.STANDARD,
        search_by_multi_columns=search_by_multi_columns,
        search_by_project_name=search_by_project_name,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )

    projects = await _aggregate_data_to_projects_from_other_sources(
        app, db_projects=db_projects, db_project_types=db_project_types, user_id=user_id
    )

    return projects, total_number_projects
