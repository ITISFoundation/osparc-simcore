import asyncio
import datetime
import logging

import arrow
from aiohttp import web
from common_library.pagination_tools import iter_pagination_params
from models_library.basic_types import IDStr
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.users import UserID
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.utils import fire_and_forget_task

from ..director_v2 import api as director_v2_api
from ..dynamic_scheduler import api as dynamic_scheduler_api
from . import _crud_api_read, projects_service
from ._access_rights_api import check_user_project_permission
from .exceptions import (
    ProjectNotFoundError,
    ProjectNotTrashedError,
    ProjectRunningConflictError,
)
from .models import ProjectDict, ProjectPatchInternalExtended

_logger = logging.getLogger(__name__)


async def _is_project_running(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
) -> bool:
    return bool(
        await director_v2_api.is_pipeline_running(
            app, user_id=user_id, project_id=project_id
        )
    ) or bool(
        await dynamic_scheduler_api.list_dynamic_services(
            app, user_id=user_id, project_id=project_id
        )
    )


async def trash_project(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    force_stop_first: bool,
    explicit: bool,
) -> None:
    """

    Raises:
        ProjectStopError:
        ProjectRunningConflictError:
    """
    await check_user_project_permission(
        app,
        project_id=project_id,
        user_id=user_id,
        product_name=product_name,
        permission="write",
    )

    if force_stop_first:

        async def _schedule():
            await asyncio.gather(
                director_v2_api.stop_pipeline(
                    app, user_id=user_id, project_id=project_id
                ),
                projects_service.remove_project_dynamic_services(
                    user_id=user_id,
                    project_uuid=f"{project_id}",
                    app=app,
                    simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                    notify_users=False,
                ),
            )

        fire_and_forget_task(
            _schedule(),
            task_suffix_name=f"trash_project_force_stop_first_{user_id=}_{project_id=}",
            fire_and_forget_tasks_collection=app[APP_FIRE_AND_FORGET_TASKS_KEY],
        )

    elif await _is_project_running(app, user_id=user_id, project_id=project_id):
        raise ProjectRunningConflictError(
            project_uuid=project_id,
            user_id=user_id,
            product_name=product_name,
        )

    await projects_service.patch_project(
        app,
        user_id=user_id,
        product_name=product_name,
        project_uuid=project_id,
        project_patch=ProjectPatchInternalExtended(
            trashed_at=arrow.utcnow().datetime,
            trashed_explicitly=explicit,
            trashed_by=user_id,
        ),
    )


async def untrash_project(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
) -> None:
    # NOTE: check_user_project_permission is inside projects_api.patch_project
    await projects_service.patch_project(
        app,
        user_id=user_id,
        product_name=product_name,
        project_uuid=project_id,
        project_patch=ProjectPatchInternalExtended(
            trashed_at=None, trashed_explicitly=False, trashed_by=None
        ),
    )


def _get_trashed_fields(project: ProjectDict):
    trashed_at = project.get("trashed")
    trashed_by = project.get("trashedBy")
    trashed_explicitly = project.get("trashedExplicitly")
    return trashed_at, trashed_by, trashed_explicitly


async def list_trashed_projects(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    until_equal_datetime: datetime.datetime | None = None,
) -> list[ProjectID]:
    """
    Lists all projects that were trashed until a specific datetime (if !=None).
    """
    trashed_projects: list[ProjectID] = []

    for page_params in iter_pagination_params(limit=100):
        (
            projects,
            page_params.total_number_of_items,
        ) = await _crud_api_read.list_projects_full_depth(
            app,
            user_id=user_id,
            product_name=product_name,
            trashed=True,
            tag_ids_list=[],
            offset=page_params.offset,
            limit=page_params.limit,
            order_by=OrderBy(field=IDStr("trashed"), direction=OrderDirection.ASC),
            search_by_multi_columns=None,
            search_by_project_name=None,
        )

        # NOTE: Applying POST-FILTERING because we do not want to modify the interface of
        # _crud_api_read.list_projects_full_depth at this time.
        # This filtering couldn't be handled at the database level when `projects_repo`
        # was refactored, as defining a custom trash_filter was needed to allow more
        # flexibility in filtering options.

        for project in projects:
            trashed_at, trashed_by, trashed_explicitly = _get_trashed_fields(project)

            if (
                trashed_at
                and (until_equal_datetime is None or trashed_at < until_equal_datetime)
                and trashed_by == user_id
                and trashed_explicitly
            ):
                trashed_projects.append(project["uuid"])

    return trashed_projects


async def delete_trashed_project(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    until_equal_datetime: datetime.datetime | None = None,
) -> None:
    """
    Deletes a project that was explicitly trashed by the user from a specific datetime (if provided, otherwise all).

    Raises:
        ProjectNotFoundError: If the project is not found.
        ProjectNotTrashedError: If the project was not trashed explicitly by the user from the specified datetime.
    """
    project = await projects_service.get_project_for_user(
        app, project_uuid=f"{project_id}", user_id=user_id
    )

    if not project:
        raise ProjectNotFoundError(project_uuid=project_id, user_id=user_id)

    trashed_at, trashed_by, trashed_explicitly = _get_trashed_fields(project)

    if (
        not trashed_at
        or (until_equal_datetime is not None and until_equal_datetime < trashed_at)
        or trashed_by != user_id
        or not trashed_explicitly
    ):
        raise ProjectNotTrashedError(
            project_uuid=project_id,
            user_id=user_id,
            reason="Project was not trashed explicitly by the user from the specified datetime",
        )
    # FIXME: locking while deleting?
    # FIXME: this can be heavy. Rather call delete_trashed_project as a task
    await projects_service.delete_project_by_user(
        app,
        user_id=user_id,
        project_uuid=project_id,
    )
