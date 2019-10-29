# pylint: disable=no-value-for-parameter

import json
import logging
import uuid
import random
import string

from aiohttp import web

from .login.decorators import RQT_USERID_KEY, login_required
from .projects.projects_api import get_project_for_user
from .projects.projects_db import APP_PROJECT_DBAPI
from .projects.projects_utils import clone_project_document
from .statics import INDEX_RESOURCE_NAME

logger = logging.getLogger(__name__)


# HANDLERS ------------------------------------------

# share/study/study_id ------------------------------------------------
@login_required
async def get_share_study_tokens(request: web.Request) -> web.Response:

    async def _process_request(request):
        study_id = request.match_info.get("study_id", None)
        if study_id is None:
            raise web.HTTPBadRequest
        user_id = request[RQT_USERID_KEY]
        return user_id, study_id

    user_id, study_id = await _process_request(request)
    source_study = await get_project_for_user(request, study_id, user_id)
    cloned_study, _nodes_map = clone_project_document(source_study)
    logger.debug("Getting sharing tokens for %s", study_id)
    token = "copy-" + str(study_id) + "_" + str(user_id)
    data = {
        'copyLink': "http://localhost:9081/v0/shared/study/" + token,
        'copyToken': token,
        'copyObject': cloned_study['workbench']
    }
    logger.debug("END OF ROUTINE. Response %s", data)
    return data

def randomString(stringLength=10):
    """Generate a random string of fixed length """
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))

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

    if "copy-" in token_id:
        pass
    else:
        raise RuntimeError("No operation found in token.")

    source_study_user_id = token_id.split("copy-",1)[1]
    data = source_study_user_id.split("_")
    source_study_id = data[0]
    source_user_id =  data[1]

    source_study = await get_project_for_user(request, source_study_id, source_user_id)

    # assign id to copy
    BASE_UUID = uuid.UUID("eb4bd593-348c-498a-a21c-9b858472a3ae")
    new_study_id = str( uuid.uuid5(BASE_UUID, source_study_id + str(user_id) + randomString(10)) )

    new_study = await clone_project(request, source_study, user_id, forced_copy_project_id=new_study_id)
    db = request.config_dict[APP_PROJECT_DBAPI]
    await db.add_project(new_study, user_id, force_project_uuid=True)
    logger.debug("Study %s copied", new_study_id)

    if redirect:
        try:
            redirect_url = request.app.router[INDEX_RESOURCE_NAME].url_for().with_fragment("/shared/study/{}".format(new_study_id))
        except KeyError:
            raise RuntimeError("Unable to serve front-end. Study has been anyway copied over to user.")

        response = web.HTTPFound(location=redirect_url)
    else:
        response = {'data': new_study_id}

    return response
