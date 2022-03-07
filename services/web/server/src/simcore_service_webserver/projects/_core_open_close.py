""" Core module: operations related with active project as open/close a project

"""

import logging
from typing import List

from aiohttp import web
from models_library.projects_state import ProjectStatus
from servicelib.utils import fire_and_forget_task

from ..resource_manager.websocket_manager import (
    PROJECT_ID_KEY,
    UserSessionID,
    managed_resource,
)
from ..users_api import get_user_name
from ._core_notify import lock_project_and_notify_state_update
from ._core_services import remove_project_dynamic_services
from ._core_states import user_has_another_client_open
from .projects_exceptions import ProjectLockError

log = logging.getLogger(__name__)


async def _clean_user_disconnected_clients(
    user_session_id_list: List[UserSessionID], app: web.Application
):
    for user_session in user_session_id_list:
        with managed_resource(
            user_session.user_id, user_session.client_session_id, app
        ) as rt:
            if await rt.get_socket_id() is None:
                log.debug(
                    "removing disconnected project of user %s/%s",
                    user_session.user_id,
                    user_session.client_session_id,
                )
                await rt.remove(PROJECT_ID_KEY)


async def try_open_project_for_user(
    user_id: int, project_uuid: str, client_session_id: str, app: web.Application
) -> bool:
    try:
        async with lock_project_and_notify_state_update(
            app,
            project_uuid,
            ProjectStatus.OPENING,
            user_id,
            await get_user_name(app, user_id),
            notify_users=False,
        ):

            with managed_resource(user_id, client_session_id, app) as rt:
                user_session_id_list: List[
                    UserSessionID
                ] = await rt.find_users_of_resource(PROJECT_ID_KEY, project_uuid)

                if not user_session_id_list:
                    # no one has the project so we lock it
                    await rt.add(PROJECT_ID_KEY, project_uuid)
                    return True

                set_user_ids = {
                    user_session.user_id for user_session in user_session_id_list
                }
                if set_user_ids.issubset({user_id}):
                    # we are the only user, remove this session from the list
                    if not await user_has_another_client_open(
                        [
                            uid
                            for uid in user_session_id_list
                            if uid != UserSessionID(user_id, client_session_id)
                        ],
                        app,
                    ):
                        # steal the project
                        await rt.add(PROJECT_ID_KEY, project_uuid)
                        await _clean_user_disconnected_clients(
                            user_session_id_list, app
                        )
                        return True
            return False

    except ProjectLockError:
        log.debug(
            "project %s/%s is currently locked", f"{user_id=}", f"{project_uuid=}"
        )
        return False


async def try_close_project_for_user(
    user_id: int,
    project_uuid: str,
    client_session_id: str,
    app: web.Application,
):
    with managed_resource(user_id, client_session_id, app) as rt:
        user_to_session_ids: List[UserSessionID] = await rt.find_users_of_resource(
            PROJECT_ID_KEY, project_uuid
        )
        # first check we have it opened now
        if UserSessionID(user_id, client_session_id) not in user_to_session_ids:
            # nothing to do the project is already closed
            log.warning(
                "project [%s] is already closed for user [%s].",
                project_uuid,
                user_id,
            )
            return
        # remove the project from our list of opened ones
        log.debug(
            "removing project [%s] from user [%s] resources", project_uuid, user_id
        )
        await rt.remove(PROJECT_ID_KEY)
    # check it is not opened by someone else
    user_to_session_ids.remove(UserSessionID(user_id, client_session_id))
    log.debug("remaining user_to_session_ids: %s", user_to_session_ids)
    if not user_to_session_ids:
        # NOTE: depending on the garbage collector speed, it might already be removing it
        fire_and_forget_task(
            remove_project_dynamic_services(user_id, project_uuid, app)
        )
    else:
        log.warning(
            "project [%s] is used by other users: [%s]. This should not be possible",
            project_uuid,
            {user_session.user_id for user_session in user_to_session_ids},
        )
