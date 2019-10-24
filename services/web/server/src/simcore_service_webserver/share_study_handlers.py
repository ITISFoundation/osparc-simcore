# pylint: disable=no-value-for-parameter

import logging

from aiohttp import web

from .login.decorators import login_required

logger = logging.getLogger(__name__)


# HANDLERS ------------------------------------------

# share/study/study_id ------------------------------------------------
# @login_required
async def get_share_study_tokens(request: web.Request) -> web.Response:

    async def _process_request(request):
        study_id = request.match_info.get("study_id", None)
        if study_id is None:
            raise web.HTTPBadRequest

        return study_id

    study_id = await _process_request(request)
    logger.debug("Getting sharing tokens for %s", study_id)
    data = {
        'copy': "https://osparc.io/share/study/copy-" + study_id,
        'share': "https://osparc.io/share/study/share-" + study_id
    }
    logger.debug("END OF ROUTINE. Response %s", data)
    return data
