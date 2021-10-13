#
#
# TODO: middlewares capturing /project/{project_id} or override routers?
#
#  - intercepts /project/{project_uuid}* requests
#  - transforms project_uuid into the correct project's version (project working copy or pwc ).
#


import logging
from typing import List, Tuple

from aiohttp import web
from aiohttp.web_middlewares import _Handler
from models_library.projects import ProjectID

from ._meta import api_version_prefix as VTAG
from .director_v2_api import AbstractProjectRunPolicy
from .meta_iterations import get_or_create_runnable_projects, get_runnable_projects_ids
from .version_control_db import VersionControlRepositoryInternalAPI
from .version_control_models import CommitID

log = logging.getLogger(__name__)


# SEE OAS
#
#  https://github.com/ITISFoundation/osparc-simcore/blob/master/services/web/server/src/simcore_service_webserver/api/v0/openapi.yaml#L8563
#
PROJECTS_API_PREFIX = f"/{VTAG}/projects/"


@web.middleware
async def projects_redirection_middleware(request: web.Request, handler: _Handler):
    """Intercepts /project/{project_id}* requests and redirect them to the copy @HEAD"""
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

    response = await handler(request)

    #
    # FIXME: any reference to project_id in the response has to be replaced by wcopy_project_id?
    # Asks for project X and returns project Y !! should instead be composed
    #

    # A solution would be to have project/*/workbench ?
    return response


class MetaProjectRunPolicy(AbstractProjectRunPolicy):
    async def get_runnable_projects_ids(
        self,
        request: web.Request,
        project_uuid: ProjectID,
    ) -> List[ProjectID]:
        return await get_runnable_projects_ids(request, project_uuid)

    async def get_or_create_runnable_projects(
        self,
        request: web.Request,
        project_uuid: ProjectID,
    ) -> Tuple[List[ProjectID], List[CommitID]]:
        return await get_or_create_runnable_projects(request, project_uuid)


meta_project_policy = MetaProjectRunPolicy()
