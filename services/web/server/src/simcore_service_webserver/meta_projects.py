""" Access to the to projects module

    - Adds a middleware to intercept /projects/* requests
    - Implements a MetaProjectRunPolicy policy (see director_v2_abc.py) to define how meta-projects run

"""


import logging
import re
from typing import List, Tuple

from aiohttp import web
from aiohttp.web_middlewares import _Handler
from models_library.basic_regex import UUID_RE
from models_library.projects import ProjectID

from ._meta import api_version_prefix as VTAG
from .director_v2_api import AbstractProjectRunPolicy
from .meta_iterations import get_or_create_runnable_projects, get_runnable_projects_ids
from .meta_version_control import CommitID, VersionControlForMetaModeling
from .projects.projects_handlers import RQ_REQUESTED_REPO_PROJECT_UUID_KEY

log = logging.getLogger(__name__)


# SEE https://github.com/ITISFoundation/osparc-simcore/blob/master/services/web/server/src/simcore_service_webserver/api/v0/openapi.yaml#L8563
URL_PATTERN = re.compile(rf"^\/{VTAG}\/projects\/({UUID_RE})[\/]{{0,1}}")


@web.middleware
async def projects_redirection_middleware(request: web.Request, handler: _Handler):
    """Intercepts /projects/{project_id}* requests and redirect them to the copy @HEAD

    Any given project has a unique identifier 'project_id' but, when activated,
    it also has a version history (denoted 'checkpoints' in the API).

    In that case, GET /projects/1234 shall refer to the HEAD version of the project
    with id 1234, also denoted the project's working copy (in short 'workcopy project')

    All metaprojects are versioned so this middleware intercepts calls to GET project
    and ensures that the response body includes the correct workcopy of the requested
    project.
    """

    if URL_PATTERN.match(f"{request.rel_url}"):
        #
        # FIXME: because hierarchical design is not guaranteed, we find ourselves with
        # entries like /v0/computation/pipeline/{project_id}:start which might also neeed
        # indirection
        #

        for path_param in ("project_id", "project_uuid"):
            # FIXME: need to enforce unique path params since
            # OAS uses both 'project_id' and also 'project_uuid'

            if project_id := request.match_info.get(path_param):

                vc_repo = VersionControlForMetaModeling(request)

                if repo_id := await vc_repo.get_repo_id(ProjectID(project_id)):
                    # Changes resolved project_id parameter with working copy instead
                    #
                    # TODO: optimize db calls
                    #
                    workcopy_project_id = await vc_repo.get_workcopy_project_id(repo_id)
                    request.match_info[path_param] = f"{workcopy_project_id}"

                    if f"{workcopy_project_id}" != f"{project_id}":
                        request[
                            RQ_REQUESTED_REPO_PROJECT_UUID_KEY
                        ] = workcopy_project_id
                        log.debug(
                            "Redirecting request with %s to working copy %s",
                            f"{project_id=}",
                            f"{workcopy_project_id=}",
                        )

                    break

    response = await handler(request)

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
