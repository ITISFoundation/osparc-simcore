# pylint: disable=no-value-for-parameter

import logging

from aiohttp import web

from .login.decorators import RQT_USERID_KEY, login_required
from .projects.projects_api import get_project_for_user
from .projects.projects_db import APP_PROJECT_DBAPI
from .statics import INDEX_RESOURCE_NAME

logger = logging.getLogger(__name__)


# HANDLERS ------------------------------------------

# shared/study/token_id --------------------------------------------------
@login_required
async def get_shared_study(request: web.Request) -> web.Response:
    from .projects.projects_api import clone_project # TODO: keep here since it is async and parser thinks it is a handler

    async def _process_request(request):
        token_id = request.match_info.get("token_id", None)
        if token_id is None:
            raise web.HTTPBadRequest
        redirect = True
        if request.query.get("redirect") in ['false', 'False']:
            redirect = False
        return token_id, redirect

    user_id = request[RQT_USERID_KEY]

    token_id, redirect = await _process_request(request)
    logger.debug("Creating study from token %s", token_id)

    if "copy-" in token_id:
        pass
    else:
        raise RuntimeError("No operation found in token.")

    source_study_user_id = token_id.split("copy-", 1)[1]
    data = source_study_user_id.split("_")
    source_study_id, source_user_id = data

    source_study = await get_project_for_user(request, source_study_id, source_user_id)

    cloned_study = await clone_project(request, source_study, user_id)
    cloned_study_id = cloned_study["uuid"]
    db = request.config_dict[APP_PROJECT_DBAPI]
    await db.add_project(cloned_study, user_id, force_project_uuid=True)
    logger.debug("Study %s copied", cloned_study_id)

    if redirect:
        try:
            redirect_url = request.app.router[INDEX_RESOURCE_NAME].url_for().with_fragment("/shared/study/{}".format(cloned_study_id))
        except KeyError:
            raise RuntimeError("Unable to serve front-end. Study has been anyway copied over to user.")

        response = web.HTTPFound(location=redirect_url)
    else:
        response = {'data': cloned_study_id}

    return response
