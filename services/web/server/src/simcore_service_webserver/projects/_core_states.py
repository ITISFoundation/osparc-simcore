""" Core submodule: project states logic

"""

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from aiohttp import web
from models_library.projects_pipeline import ComputationTask
from models_library.projects_state import (
    Owner,
    ProjectLocked,
    ProjectRunningState,
    ProjectState,
    ProjectStatus,
    RunningState,
)
from servicelib.utils import logged_gather

from .. import director_v2_api
from ..resource_manager.websocket_manager import (
    PROJECT_ID_KEY,
    UserSessionID,
    managed_resource,
)
from ..users_api import get_user_name
from .project_lock import UserNameDict, get_project_locked_state

log = logging.getLogger(__name__)


async def user_has_another_client_open(
    user_session_id_list: List[UserSessionID], app: web.Application
) -> bool:
    # NOTE: this is not in _core_open_close because
    # NOTE if there is an active socket in use, that means the client is active
    for user_session in user_session_id_list:
        with managed_resource(
            user_session.user_id, user_session.client_session_id, app
        ) as rt:
            if await rt.get_socket_id() is not None:
                return True
    return False


async def _get_project_lock_state(
    user_id: int,
    project_uuid: str,
    app: web.Application,
) -> ProjectLocked:
    """returns the lock state of a project
    1. If a project is locked for any reason, first return the project as locked and STATUS defined by lock
    2. If a client_session_id is passed, then first check to see if the project is currently opened by this very user/tab combination, if yes returns the project as Locked and OPENED.
    3. If any other user than user_id is using the project (even disconnected before the TTL is finished) then the project is Locked and OPENED.
    4. If the same user is using the project with a valid socket id (meaning a tab is currently active) then the project is Locked and OPENED.
    5. If the same user is using the project with NO socket id (meaning there is no current tab active) then the project is Unlocked and OPENED. which means the user can open it again.
    """
    log.debug(
        "getting project [%s] lock state for user [%s]...",
        f"{project_uuid=}",
        f"{user_id=}",
    )
    prj_locked_state: Optional[ProjectLocked] = await get_project_locked_state(
        app, project_uuid
    )
    if prj_locked_state:
        log.debug(
            "project [%s] is locked: %s", f"{project_uuid=}", f"{prj_locked_state=}"
        )
        return prj_locked_state

    # let's now check if anyone has the project in use somehow
    with managed_resource(user_id, None, app) as rt:
        user_session_id_list: List[UserSessionID] = await rt.find_users_of_resource(
            PROJECT_ID_KEY, project_uuid
        )
    set_user_ids = {user_session.user_id for user_session in user_session_id_list}

    assert (  # nosec
        len(set_user_ids) <= 1
    )  # nosec  # NOTE: A project can only be opened by one user in one tab at the moment

    if not set_user_ids:
        # no one has the project, so it is unlocked and closed.
        log.debug("project [%s] is not in use", f"{project_uuid=}")
        return ProjectLocked(value=False, status=ProjectStatus.CLOSED)

    log.debug(
        "project [%s] might be used by the following users: [%s]",
        f"{project_uuid=}",
        f"{set_user_ids=}",
    )
    usernames: List[UserNameDict] = [
        await get_user_name(app, uid) for uid in set_user_ids
    ]
    # let's check if the project is opened by the same user, maybe already opened or closed in a orphaned session
    if set_user_ids.issubset({user_id}):
        if not await user_has_another_client_open(user_session_id_list, app):
            # in this case the project is re-openable by the same user until it gets closed
            log.debug(
                "project [%s] is in use by the same user [%s] that is currently disconnected, so it is unlocked for this specific user and opened",
                f"{project_uuid=}",
                f"{set_user_ids=}",
            )
            return ProjectLocked(
                value=False,
                owner=Owner(user_id=list(set_user_ids)[0], **usernames[0]),
                status=ProjectStatus.OPENED,
            )
    # the project is opened in another tab or browser, or by another user, both case resolves to the project being locked, and opened
    log.debug(
        "project [%s] is in use by another user [%s], so it is locked",
        f"{project_uuid=}",
        f"{set_user_ids=}",
    )
    return ProjectLocked(
        value=True,
        owner=Owner(user_id=list(set_user_ids)[0], **usernames[0]),
        status=ProjectStatus.OPENED,
    )


async def get_project_states_for_user(
    user_id: int, project_uuid: str, app: web.Application
) -> ProjectState:
    # for templates: the project is never locked and never opened. also the running state is always unknown
    lock_state = ProjectLocked(value=False, status=ProjectStatus.CLOSED)
    running_state = RunningState.UNKNOWN

    computation_task: Optional[ComputationTask]

    lock_state, computation_task = await logged_gather(
        _get_project_lock_state(user_id, project_uuid, app),
        director_v2_api.get_computation_task(app, user_id, UUID(project_uuid)),
    )

    if computation_task:
        # get the running state
        running_state = computation_task.state

    return ProjectState(
        locked=lock_state, state=ProjectRunningState(value=running_state)
    )


async def add_project_states_for_user(
    user_id: int,
    project: Dict[str, Any],
    is_template: bool,
    app: web.Application,
) -> Dict[str, Any]:
    log.debug(
        "adding project states for %s with project %s",
        f"{user_id=}",
        f"{project['uuid']=}",
    )
    # for templates: the project is never locked and never opened. also the running state is always unknown
    lock_state = ProjectLocked(value=False, status=ProjectStatus.CLOSED)
    running_state = RunningState.UNKNOWN

    if not is_template:
        lock_state = await _get_project_lock_state(user_id, project["uuid"], app)

        if computation_task := await director_v2_api.get_computation_task(
            app, user_id, project["uuid"]
        ):
            # get the running state
            running_state = computation_task.state
            # get the nodes individual states
            for (
                node_id,
                node_state,
            ) in computation_task.pipeline_details.node_states.items():
                prj_node = project["workbench"].get(str(node_id))
                if prj_node is None:
                    continue
                node_state_dict = json.loads(
                    node_state.json(by_alias=True, exclude_unset=True)
                )
                prj_node.setdefault("state", {}).update(node_state_dict)

    project["state"] = ProjectState(
        locked=lock_state, state=ProjectRunningState(value=running_state)
    ).dict(by_alias=True, exclude_unset=True)
    return project
