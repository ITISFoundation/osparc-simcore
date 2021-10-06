#
#
# TODO: middlewares capturing /project/{project_id} or override routers?
#
#  - intercepts /project/{project_uuid}* requests
#  - transforms project_uuid into the correct project's version (project working copy or pwc ).
#


import logging

from aiohttp import web
from aiohttp.web_middlewares import _Handler, middleware
from models_library.projects import ProjectID

from ._meta import api_version_prefix as VTAG
from .version_control_db import VersionControlRepositoryInternalAPI

log = logging.getLogger(__name__)


# SEE OAS
#
#  https://github.com/ITISFoundation/osparc-simcore/blob/master/services/web/server/src/simcore_service_webserver/api/v0/openapi.yaml#L8563
#
PROJECTS_API_PREFIX = f"/{VTAG}/projects/"


@middleware
async def projects_redirection_middleware(request: web.Request, handler: _Handler):
    """Intercepts /project/{project_id}* requests and change
    the project_id parameter but the current working copy @HEAD
    """
    if str(request.rel_url).startswith(PROJECTS_API_PREFIX):

        try:
            project_id = ProjectID(request.match_info["project_id"])

            # find current working copy
            vc_repo = VersionControlRepositoryInternalAPI(request)

            # TODO: optimize db calls
            if repo_id := await vc_repo.get_repo_id(project_id):
                #
                # Changes resolved project_id parameter with working copy instead
                #
                wcopy_project_id = await vc_repo.get_wcopy_project_id(repo_id)
                request.match_info["project_id"] = str(wcopy_project_id)

                log.debug(
                    "Redirecting project '%s' to working copy '%s'",
                    project_id,
                    wcopy_project_id,
                )
        except KeyError as err:
            log.debug("Skips redirection of %s: %s", request, err)

    return await handler(request)
