""" Handlers to /computation/pipeline routes

"""

import logging

from aiohttp import web

from models_library.projects import RunningState
from servicelib.request_keys import RQT_USERID_KEY

from .computation_api import (
    get_pipeline_state,
    start_pipeline_computation,
    update_pipeline_db,
)
from .login.decorators import login_required
from .projects.projects_api import get_project_for_user
from .projects.projects_exceptions import ProjectNotFoundError
from .security_api import check_permission

log = logging.getLogger(__file__)


async def _process_request(request):
    # TODO: PC->SAN why validation is commented???
    # params, query, body = await extract_and_validate(request)
    project_id = request.match_info.get("project_id", None)
    if project_id is None:
        raise web.HTTPBadRequest

    user_id = request[RQT_USERID_KEY]

    return user_id, project_id


# HANDLERS ------------------------------------------


@login_required
async def start_pipeline(request: web.Request) -> web.Response:
    """Starts pipeline described in the workbench section of a valid project
    already at the server side
    """
    await check_permission(request, "services.pipeline.*")
    await check_permission(request, "project.read")

    user_id, project_id = await _process_request(request)

    # FIXME: if start is already ongoing. Do not re-start!
    try:
        project = await get_project_for_user(request.app, project_id, user_id)

        pipeline_state: RunningState = await get_pipeline_state(request.app, project_id)

        if pipeline_state in [
            RunningState.PUBLISHED,
            RunningState.PENDING,
            RunningState.STARTED,
            RunningState.RETRY,
        ]:
            raise web.HTTPForbidden(
                reason=f"Projet {project_id} already started, state {pipeline_state}"
            )

        await update_pipeline_db(request.app, project_id, project["workbench"])

    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {project_id} not found") from exc

    task_id = await start_pipeline_computation(request.app, user_id, project_id)

    # answer the client while task has been spawned
    data = {
        # TODO: PC->SAN: some name with task id. e.g. to distinguish two projects with identical pipeline?
        "pipeline_name": "request_data",
        "project_id": project_id,
        "task_id": task_id if task_id else "failed to start",
    }
    return data
