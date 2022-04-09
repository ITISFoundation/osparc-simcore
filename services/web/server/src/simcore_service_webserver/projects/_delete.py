""" Implements logic to delete a project (and all associated services, data, etc)

"""

import asyncio
import logging
from typing import Callable, List

from aiohttp import web
from models_library.projects import ProjectID
from models_library.users import UserID

from .. import director_v2_api
from ..storage_api import delete_data_folders_of_project
from ..users_exceptions import UserNotFoundError
from .projects_db import APP_PROJECT_DBAPI, ProjectDBAPI
from .projects_exceptions import (
    ProjectDeleteError,
    ProjectLockError,
    ProjectNotFoundError,
)

log = logging.getLogger(__name__)

DELETE_PROJECT_TASK_NAME = "fire_and_forget.delete_project.project_uuid={0}.user_id={1}"


async def mark_project_as_deleted(app: web.Application, project_uuid: ProjectID):
    """
    ::raises ProjectNotFoundError
    """
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    # TODO: tmp using invisible as a "deletion mark"
    # Even if any of the steps below fail, the project will remain invisible
    # TODO: see https://github.com/ITISFoundation/osparc-simcore/pull/2522

    # TODO: note that if any of the steps below fail, it might results in a
    # services/projects/data that might be incosistent. The GC should
    # be able to detect that and resolve it.
    await db.set_hidden_flag(project_uuid, enabled=True)


async def delete_project(
    app: web.Application,
    project_uuid: ProjectID,
    user_id: UserID,
    # TODO: this function was tmp added here to avoid refactoring all projects_api in a single PR
    remove_project_dynamic_services: Callable,
) -> None:
    """Stops dynamic services, deletes data and finally deletes project

    NOTE: this does NOT use fire&forget anymore. This is a decision of the caller to make.

    raises ProjectDeleteError
    """

    log.debug(
        "Deleting project '%s' for user '%s' in database",
        f"{project_uuid=}",
        f"{user_id=}",
    )
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    try:
        await mark_project_as_deleted(app, project_uuid)

        # stops dynamic services
        # - raises ProjectNotFoundError, UserNotFoundError, ProjectLockError
        await remove_project_dynamic_services(
            user_id, project_uuid, app, notify_users=False
        )

        # stops computational services
        # - raises DirectorServiceError
        await director_v2_api.delete_pipeline(app, user_id, project_uuid)

        # rm data from storage
        await delete_data_folders_of_project(app, project_uuid, user_id)

        # rm project from database
        await db.delete_user_project(user_id, f"{project_uuid}")

    except ProjectLockError as err:
        raise ProjectDeleteError(
            project_uuid, reason=f"Project currently in use {err}"
        ) from err

    except (ProjectNotFoundError, UserNotFoundError) as err:
        raise ProjectDeleteError(
            project_uuid, reason=f"Invalid project state {err}"
        ) from err


def create_delete_project_background_task(
    app: web.Application,
    project_uuid: ProjectID,
    user_id: UserID,
    remove_project_dynamic_services: Callable,
    logger: logging.Logger,
) -> asyncio.Task:
    """Wrap `delete_project` for a `project_uuid` and `user_id` into a Task and schedule its execution in the event loop.

    Return the scheduled Task
    """

    def _log_errors(fut: asyncio.Future):
        try:
            fut.result()
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                f"Error while deleting {project_uuid=} owned by {user_id=}"
            )

    task = asyncio.create_task(
        delete_project(app, project_uuid, user_id, remove_project_dynamic_services),
        name=DELETE_PROJECT_TASK_NAME.format(project_uuid, user_id),
    )

    assert task.get_name() == DELETE_PROJECT_TASK_NAME.format(  # nosec
        project_uuid, user_id
    )

    task.add_done_callback(_log_errors)
    return task


def get_delete_project_background_tasks(
    project_uuid: ProjectID, user_id: UserID
) -> List[asyncio.Task]:
    """Returns delete-project task if not yet finished"""
    return [
        task
        for task in asyncio.all_tasks()
        if task.get_name() == DELETE_PROJECT_TASK_NAME.format(project_uuid, user_id)
    ]


def is_delete_project_background_task_running(
    project_uuid: ProjectID, user_id: UserID
) -> bool:
    tasks = get_delete_project_background_tasks(project_uuid, user_id)
    assert len(tasks) <= 1  # nosec
    return len(tasks) > 0
