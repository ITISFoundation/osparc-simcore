"""Implements logic to delete a project (and all associated services, data, etc)


NOTE: this entire module is protected within the `projects` package
    and ONLY to be used in the implementation of the project_api module's functions
"""

import asyncio
import logging
from typing import Protocol

from aiohttp import web
from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
from servicelib.utils import fire_and_forget_task

from ..director_v2 import director_v2_service
from ..storage.api import delete_data_folders_of_project
from ..users.exceptions import UserNotFoundError
from ..users.users_service import FullNameDict
from . import _projects_repository
from ._access_rights_service import check_user_project_permission
from ._projects_repository_legacy import ProjectDBAPI
from .exceptions import (
    ProjectDeleteError,
    ProjectInvalidRightsError,
    ProjectLockError,
    ProjectNotFoundError,
)

_logger = logging.getLogger(__name__)

_DELETE_PROJECT_TASK_NAME = (
    "background-task.delete_project/project_uuid={0}.user_id={1}"
)


class RemoveProjectServicesCallable(Protocol):
    # NOTE: this function was tmp added here to avoid refactoring all projects_api in a single PR
    async def __call__(
        self,
        user_id: int,
        project_uuid: str,
        app: web.Application,
        simcore_user_agent: str,
        *,
        notify_users: bool = True,
        user_name: FullNameDict | None = None,
    ) -> None: ...


async def mark_project_as_deleted(
    app: web.Application, project_uuid: ProjectID, user_id: UserID
):
    """
    ::raises ProjectInvalidRightsError
    ::raises ProjectNotFoundError
    """
    # NOTE: https://github.com/ITISFoundation/osparc-issues/issues/468
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)
    product_name = await db.get_project_product(project_uuid=project_uuid)
    await check_user_project_permission(
        app,
        project_id=project_uuid,
        user_id=user_id,
        product_name=product_name,
        permission="delete",
    )

    await db.check_project_has_only_one_product(project_uuid)

    # NOTE: if any of the steps below fail, it might results in a
    # services/projects/data that might be incosistent. The GC should
    # be able to detect that and resolve it.
    await _projects_repository.patch_project(
        app,
        project_uuid=project_uuid,
        new_partial_project_data={"hidden": True},
    )


async def delete_project(
    app: web.Application,
    project_uuid: ProjectID,
    user_id: UserID,
    simcore_user_agent: str,
    remove_project_dynamic_services: RemoveProjectServicesCallable,
) -> None:
    """Stops dynamic services, deletes data and finally deletes project

    NOTE: this does NOT use fire&forget anymore. This is a decision of the caller to make.

    raises ProjectDeleteError
    """

    _logger.debug(
        "Deleting project '%s' for user '%s' in database",
        f"{project_uuid=}",
        f"{user_id=}",
    )
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    try:
        # NOTE: Project access rights are checked inside this function
        await mark_project_as_deleted(app, project_uuid, user_id)

        # stops dynamic services
        # - raises ProjectNotFoundError, UserNotFoundError, ProjectLockError
        await remove_project_dynamic_services(
            user_id=user_id,
            project_uuid=f"{project_uuid}",
            app=app,
            simcore_user_agent=simcore_user_agent,
            notify_users=False,
        )

        # stops computational services
        # - raises DirectorServiceError
        await director_v2_service.delete_pipeline(app, user_id, project_uuid)

        # rm data from storage
        await delete_data_folders_of_project(app, project_uuid, user_id)

        # rm project from database
        await db.delete_project(user_id, f"{project_uuid}")

    except ProjectLockError as err:
        raise ProjectDeleteError(
            project_uuid=project_uuid, reason=f"Project currently in use {err}"
        ) from err

    except (ProjectInvalidRightsError, ProjectNotFoundError, UserNotFoundError) as err:
        raise ProjectDeleteError(
            project_uuid=project_uuid, reason=f"Invalid project state {err}"
        ) from err


def schedule_task(
    app: web.Application,
    project_uuid: ProjectID,
    user_id: UserID,
    simcore_user_agent: str,
    remove_project_dynamic_services: RemoveProjectServicesCallable,
    logger: logging.Logger,
) -> asyncio.Task:
    """Wrap `delete_project` for a `project_uuid` and `user_id` into a Task
        and schedule its execution in the event loop.

    Return the scheduled Task
    """

    def _log_state_when_done(fut: asyncio.Future):
        # the task created in the parent function is typically used
        # to fire&forget therefore this internal function will be used as
        # callback to provide a minimal log that informs about the
        # state of the task when completed.
        try:
            fut.result()
            logger.info(
                "Deleted %s using %s permissions", f"{project_uuid=}", f"{user_id=}"
            )

        except asyncio.exceptions.CancelledError:
            logger.warning(
                "Canceled deletion of %s using %s permissions",
                f"{project_uuid=}",
                f"{user_id=}",
            )
            raise

        except ProjectDeleteError:
            logger.exception(
                "Failed to delete %s using %s permissions",
                f"{project_uuid=}",
                f"{user_id=}",
            )

        except ProjectInvalidRightsError:
            logger.exception(
                "%s does not have permission to delete %s",
                f"{user_id=}",
                f"{project_uuid=}",
            )

        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Unexpected error while deleting %s with %spermissions",
                f"{project_uuid=}",
                f"{user_id=}",
            )

    # ------
    task = fire_and_forget_task(
        delete_project(
            app,
            project_uuid,
            user_id,
            simcore_user_agent,
            remove_project_dynamic_services,
        ),
        task_suffix_name=_DELETE_PROJECT_TASK_NAME.format(project_uuid, user_id),
        fire_and_forget_tasks_collection=app[APP_FIRE_AND_FORGET_TASKS_KEY],
    )

    assert task in get_scheduled_tasks(project_uuid, user_id)  # nosec

    task.add_done_callback(_log_state_when_done)
    return task


def get_scheduled_tasks(project_uuid: ProjectID, user_id: UserID) -> list[asyncio.Task]:
    """Returns tasks matching delete-project task's name."""
    return [
        task
        for task in asyncio.all_tasks()
        if task.get_name().endswith(
            _DELETE_PROJECT_TASK_NAME.format(project_uuid, user_id)
        )
    ]
