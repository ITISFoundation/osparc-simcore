""" Core submodule: logic to delete a project (and all associated services, data, etc)

"""

import asyncio
import functools
import logging
from uuid import UUID

from aiohttp import web
from servicelib.utils import log_exception_callback

from .. import director_v2_api
from ..storage_api import delete_data_folders_of_project
from ._core_services import remove_project_dynamic_services
from .projects_db import APP_PROJECT_DBAPI, ProjectDBAPI

log = logging.getLogger(__name__)

# helper to format task name when using fire&forget
# TODO: might use this to ensure only ONE task instance is fire&forget at a time
DELETE_PROJECT_TASK_NAME = "fire_and_forget.delete_project.project_uuid={0}.user_id={1}"


async def delete_project(app: web.Application, project_uuid: str, user_id: int) -> None:
    """Stops dynamic services, deletes data and finally deletes project

    NOTE: this does NOT use fire&forget anymore. This is a decission of the caller to make.

    raises ProjectLockError
    raises ProjectNotFoundError
    raises UserNotFoundError
    raises DirectorServiceError
    """
    log.debug(
        "deleting project '%s' for user '%s' in database",
        f"{project_uuid=}",
        f"{user_id=}",
    )
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    # TODO: tmp using invisible as a "deletion mark"
    # Even if any of the steps below fail, the project will remain invisible
    await db.set_hidden_flag(f"{project_uuid}", enabled=True)

    # stops dynamic services
    # raises ProjectNotFoundError, UserNotFoundError, ProjectLockError
    await remove_project_dynamic_services(
        user_id, project_uuid, app, notify_users=False
    )

    # stops computational services
    # raises DirectorServiceError
    await director_v2_api.delete_pipeline(app, user_id, UUID(project_uuid))

    # rm data from storage
    # NOTE: here project_uuid/user_id are needed for storage
    await delete_data_folders_of_project(app, project_uuid, user_id)

    # rm project from database
    await db.delete_user_project(user_id, project_uuid)


def create_delete_project_task(
    app: web.Application, project_uuid: str, user_id: int
) -> asyncio.Task:
    """helper to create homogenously delete_project tasks"""

    task = asyncio.create_task(
        delete_project(app, project_uuid, user_id),
        name=DELETE_PROJECT_TASK_NAME.format(project_uuid, user_id),
    )

    task.add_done_callback(functools.partial(log_exception_callback, log))
    return task
