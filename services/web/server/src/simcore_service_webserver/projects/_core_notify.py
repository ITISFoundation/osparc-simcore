""" Core submodule: utils for project events like notifications, or observer pattern, etc

"""
import contextlib
import logging
from typing import List

from aiohttp import web
from models_library.projects_state import ProjectState, ProjectStatus
from servicelib.observer import observe
from servicelib.utils import logged_gather

from ..resource_manager.websocket_manager import PROJECT_ID_KEY, managed_resource
from ._core_get import get_project_for_user
from ._core_nodes import notify_project_state_update
from ._core_states import get_project_states_for_user
from .project_lock import UserNameDict, lock_project
from .projects_exceptions import ProjectLockError

log = logging.getLogger(__name__)


async def retrieve_and_notify_project_locked_state(
    user_id: int,
    project_uuid: str,
    app: web.Application,
    notify_only_prj_user: bool = False,
):
    project = await get_project_for_user(app, project_uuid, user_id, include_state=True)
    await notify_project_state_update(
        app, project, notify_only_user=user_id if notify_only_prj_user else None
    )


@observe(event="SIGNAL_USER_DISCONNECTED")
async def user_disconnected(
    user_id: int, client_session_id: str, app: web.Application
) -> None:
    # check if there is a project resource
    with managed_resource(user_id, client_session_id, app) as rt:
        list_projects: List[str] = await rt.find(PROJECT_ID_KEY)

    await logged_gather(
        *[
            retrieve_and_notify_project_locked_state(
                user_id, prj, app, notify_only_prj_user=True
            )
            for prj in list_projects
        ]
    )


@contextlib.asynccontextmanager
async def lock_project_and_notify_state_update(
    app: web.Application,
    project_uuid: str,
    status: ProjectStatus,
    user_id: int,
    user_name: UserNameDict,
    notify_users: bool = True,
):
    """
    raises ProjectLockError
    raises ProjectNotFoundError
    raises UserNotFoundError
    raises jsonschema.ValidationError
    """

    # FIXME: PC: I find this function very error prone. For instance, the requirements
    # on the input parameters depend on the value of 'notify_users', i.e. changes dynamically.
    #
    # If notify_users=True, then project_uuid has to be defined in the database since
    # the notification function the state which is in the database. On the other hand,
    # locking relies on the project entry in redis.
    #
    # These two references to the project (redis and the db) are not in sync leading to some. An
    # example is ``stop_service`` where incosistent states that heavily depend on the logic of the function.
    #
    # A suggestion would be to split this in two explicit functions where notifications is active or not
    # but not leave that decision to a variable.
    #
    try:
        async with await lock_project(
            app,
            project_uuid,
            status,
            user_id,
            user_name,
        ):
            log.debug(
                "Project [%s] lock acquired with %s, %s, %s",
                f"{project_uuid=}",
                f"{status=}",
                f"{user_id=}",
                f"{notify_users=}",
            )
            if notify_users:
                # notifies as locked
                await retrieve_and_notify_project_locked_state(
                    user_id, project_uuid, app
                )

            yield  # none of the operations within the context can modify project

        log.debug(
            "Project [%s] lock released",
            f"{project_uuid=}",
        )
    except ProjectLockError:
        # someone else has already the lock?
        # FIXME: this can raise as well
        prj_states: ProjectState = await get_project_states_for_user(
            user_id, project_uuid, app
        )
        log.error(
            "Project [%s] for %s already locked in state '%s'. Please check with support.",
            f"{project_uuid=}",
            f"{user_id=}",
            f"{prj_states.locked.status=}",
        )
        raise

    finally:
        if notify_users:
            # notifies as lock is released
            await retrieve_and_notify_project_locked_state(user_id, project_uuid, app)
