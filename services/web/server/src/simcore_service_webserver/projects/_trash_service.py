import logging
from datetime import UTC, datetime

import arrow
from aiohttp import web
from common_library.pagination_tools import iter_pagination_params
from models_library.basic_types import IDStr
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
from models_library.users import UserID
from models_library.workspaces import WorkspaceID
from servicelib.utils import fire_and_forget_task

from ..constants import APP_FIRE_AND_FORGET_TASKS_KEY
from ..director_v2 import director_v2_service
from ..dynamic_scheduler import api as dynamic_scheduler_service
from . import _access_rights_service, _crud_api_read, _projects_repository, _projects_service, _projects_service_delete
from .exceptions import (
    ProjectNotFoundError,
    ProjectNotTrashedError,
    ProjectRunningConflictError,
    ProjectsBatchDeleteError,
)
from .models import ProjectDict, ProjectPatchInternalExtended, ProjectTypeAPI

_logger = logging.getLogger(__name__)


async def _is_project_running(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
) -> bool:
    return bool(await director_v2_service.is_pipeline_running(app, user_id=user_id, project_id=project_id)) or bool(
        await dynamic_scheduler_service.list_dynamic_services(app, user_id=user_id, project_id=project_id)
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
    await _access_rights_service.check_user_project_permission(
        app,
        project_id=project_id,
        user_id=user_id,
        product_name=product_name,
        permission="write",
    )

    if force_stop_first:
        fire_and_forget_task(
            _projects_service_delete.batch_stop_services_in_project(
                app, user_id=user_id, project_uuid=project_id, product_name=product_name
            ),
            task_suffix_name=f"trash_project_force_stop_first_{user_id=}_{project_id=}",
            fire_and_forget_tasks_collection=app[APP_FIRE_AND_FORGET_TASKS_KEY],
        )

    elif await _is_project_running(app, user_id=user_id, project_id=project_id):
        raise ProjectRunningConflictError(
            project_uuid=project_id,
            user_id=user_id,
            product_name=product_name,
        )

    await _projects_service.patch_project_for_user(
        app,
        user_id=user_id,
        product_name=product_name,
        project_uuid=project_id,
        project_patch=ProjectPatchInternalExtended(
            trashed_at=arrow.utcnow().datetime,
            trashed_explicitly=explicit,
            trashed_by=user_id,
        ),
        client_session_id=None,
    )


async def untrash_project(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
) -> None:
    # NOTE: check_user_project_permission is inside projects_api.patch_project
    await _projects_service.patch_project_for_user(
        app,
        user_id=user_id,
        product_name=product_name,
        project_uuid=project_id,
        project_patch=ProjectPatchInternalExtended(trashed_at=None, trashed_explicitly=False, trashed_by=None),
        client_session_id=None,
    )


async def mark_for_immediate_deletion(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
) -> None:
    """Hides the project and stamps it as trashed (using an epoch sentinel) so
    that the next run of the periodic garbage-collector (`safe_delete_expired_trash_as_admin`)
    picks it up and deletes it right away, bypassing `TRASH_RETENTION_DAYS`.

    This replaces the former in-process fire-and-forget deletion workflow: the actual
    removal (stop services, delete pipeline, delete storage, delete DB row) is now
    performed exclusively by `_projects_service_delete.delete_project_as_admin`,
    invoked by the garbage collector. This makes deletion durable across webserver
    restarts, since nothing here depends on an in-memory asyncio task surviving.

    ::raises ProjectInvalidRightsError
    ::raises ProjectNotFoundError
    """
    await _access_rights_service.check_user_project_permission(
        app,
        project_id=project_id,
        user_id=user_id,
        product_name=product_name,
        permission="delete",
    )

    # NOTE: if the steps performed later by the GC fail, it might result in a
    # services/projects/data that might be inconsistent. The GC retries every cycle
    # until it succeeds (see `delete_project_as_admin`).
    await _projects_repository.patch_project(
        app,
        project_uuid=project_id,
        new_partial_project_data={
            "hidden": True,
            "trashed": datetime(1970, 1, 1, tzinfo=UTC),
            "trashed_explicitly": True,
            "trashed_by": user_id,
        },
    )


def _can_delete(
    project: ProjectDict,
    user_id: UserID,
    until_equal_datetime: datetime | None,
) -> bool:
    """
    This is the current policy to delete trashed project

    """
    trashed_at = project.get("trashed")
    trashed_by = project.get("trashedBy")
    trashed_explicitly = project.get("trashedExplicitly")

    assert trashed_at is not None  # nosec
    assert trashed_by is not None  # nosec

    is_shared = len(project["accessRights"]) > 1

    return bool(
        trashed_at
        and (until_equal_datetime is None or trashed_at < until_equal_datetime)
        # NOTE: current policy is more restricted until
        # logic is adapted to deal with the other cases
        and trashed_by == user_id
        and not is_shared
        and trashed_explicitly
    )


async def list_explicitly_trashed_projects(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    until_equal_datetime: datetime | None = None,
) -> list[ProjectID]:
    """
    Lists all projects that were trashed until a specific datetime (if !=None).
    """
    trashed_projects: list[ProjectID] = []

    for page_params in iter_pagination_params(offset=0, limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE):
        (
            projects,
            page_params.total_number_of_items,
        ) = await _crud_api_read.list_projects_full_depth(
            app,
            user_id=user_id,
            product_name=product_name,
            trashed=True,
            filter_by_project_type=ProjectTypeAPI.user,
            filter_by_template_type=None,
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
        trashed_projects.extend(
            [project["uuid"] for project in projects if _can_delete(project, user_id, until_equal_datetime)]
        )
    return trashed_projects


async def delete_explicitly_trashed_project(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    product_name: ProductName,
    until_equal_datetime: datetime | None = None,
) -> None:
    """
    Deletes a project that was explicitly trashed by the user from a specific datetime (if provided, otherwise all).

    Raises:
        ProjectNotFoundError: If the project is not found.
        ProjectNotTrashedError: If the project was not trashed explicitly by the user from the specified datetime.
    """
    project = await _projects_service.get_project_for_user(app, project_uuid=f"{project_id}", user_id=user_id)

    if not project:
        raise ProjectNotFoundError(project_uuid=project_id, user_id=user_id)

    if not _can_delete(project, user_id, until_equal_datetime):
        # safety check
        raise ProjectNotTrashedError(
            project_uuid=project_id,
            user_id=user_id,
            details="Cannot delete trashed project since it does not fit current criteria",
        )

    await mark_for_immediate_deletion(
        app,
        product_name=product_name,
        user_id=user_id,
        project_id=project_id,
    )


async def batch_delete_trashed_projects_as_admin(
    app: web.Application,
    *,
    trashed_before: datetime,
    fail_fast: bool,
) -> list[ProjectID]:
    deleted_project_ids: list[ProjectID] = []
    errors: list[tuple[ProjectID, Exception]] = []

    for page_params in iter_pagination_params(offset=0, limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE):
        (
            page_params.total_number_of_items,
            expired_trashed_projects,
        ) = await _projects_repository.list_projects_db_get_as_admin(
            app,
            # both implicit and explicitly trashed
            trashed_before=trashed_before,
            offset=page_params.offset,
            limit=page_params.limit,
            order_by=_projects_repository.OLDEST_TRASHED_FIRST,
        )
        # BATCH delete
        for project in expired_trashed_projects:
            assert project.trashed  # nosec

            try:
                await _projects_service_delete.delete_project_as_admin(
                    app,
                    project_uuid=project.uuid,
                    product_name=project.product_name,
                )
                deleted_project_ids.append(project.uuid)
            except Exception as err:  # pylint: disable=broad-exception-caught
                if fail_fast:
                    raise
                errors.append((project.uuid, err))

    if errors:
        raise ProjectsBatchDeleteError(
            errors=errors,
            trashed_before=trashed_before,
            deleted_project_ids=deleted_project_ids,
        )

    return deleted_project_ids


async def batch_delete_projects_in_root_workspace_as_admin(
    app: web.Application,
    *,
    workspace_id: WorkspaceID,
    fail_fast: bool,
) -> list[ProjectID]:
    """
    Deletes all projects in the workspace root.

    Raises:
        ProjectsBatchDeleteError: If there are errors during the deletion process.
    """
    deleted_project_ids: list[ProjectID] = []
    errors: list[tuple[ProjectID, Exception]] = []

    for page_params in iter_pagination_params(offset=0, limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE):
        (
            page_params.total_number_of_items,
            projects_for_deletion,
        ) = await _projects_repository.list_projects_db_get_as_admin(
            app,
            shared_workspace_id=workspace_id,  # <-- Workspace filter
            offset=page_params.offset,
            limit=page_params.limit,
            order_by=OrderBy(field=IDStr("id")),
        )
        # BATCH delete
        for project in projects_for_deletion:
            try:
                await _projects_service_delete.delete_project_as_admin(
                    app,
                    project_uuid=project.uuid,
                    product_name=project.product_name,
                )
                deleted_project_ids.append(project.uuid)
            except Exception as err:  # pylint: disable=broad-exception-caught
                if fail_fast:
                    raise
                errors.append((project.uuid, err))

    if errors:
        raise ProjectsBatchDeleteError(
            errors=errors,
            deleted_project_ids=deleted_project_ids,
        )

    return deleted_project_ids
