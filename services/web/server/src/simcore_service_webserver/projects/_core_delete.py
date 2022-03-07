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
from .projects_db import APP_PROJECT_DBAPI

log = logging.getLogger(__name__)


async def _delete_project_from_db(
    app: web.Application, project_uuid: str, user_id: int
) -> None:
    log.debug(
        "deleting project '%s' for user '%s' in database",
        f"{project_uuid=}",
        f"{user_id=}",
    )
    db = app[APP_PROJECT_DBAPI]
    await director_v2_api.delete_pipeline(app, user_id, UUID(project_uuid))
    await db.delete_user_project(user_id, project_uuid)


async def delete_project(
    app: web.Application, project_uuid: str, user_id: int
) -> asyncio.Task:
    """It delets the project in two steps:

    - awaits deletion of the project from the db table
    - schedules a background task to rm services and stored data (as fire&forget)


    raises ProjectLockError
    """
    # TODO: mark as deleted instead of delete!!!
    await mark_as_deleted()

    await remove_project_dynamic_services(
        user_id, project_uuid, app, notify_users=False
    )
    # Here project_uuid/user_id are needed for storage
    await delete_data_folders_of_project(app, project_uuid, user_id)

    await _delete_project_from_db(app, project_uuid, user_id)

    # delete the rest (data & services) in the background
    task = asyncio.create_task(_heavy_delete(), name="delete_project.fire_and_forget")
    task.add_done_callback(functools.partial(log_exception_callback, log))
    return task
