#
#
# TODO: middlewares capturing /project/{project_id} or override routers?
#
#  - intercepts /project/{project_uuid}* requests
#  - transforms project_uuid into the correct project's version (project working copy or pwc ).
#


import json
import logging
import re
from typing import Callable, Dict, List, Optional, Tuple

from aiohttp import web
from aiohttp.web_middlewares import _Handler
from models_library.basic_regex import UUID_RE
from models_library.projects import ProjectID
from servicelib.json_serialization import json_dumps

from ._meta import api_version_prefix as VTAG
from .director_v2_api import AbstractProjectRunPolicy
from .meta_iterations import get_or_create_runnable_projects, get_runnable_projects_ids
from .projects.projects_handlers import RQ_REQUESTED_REPO_PROJECT_UUID_KEY
from .version_control_db import VersionControlForMetaModeling
from .version_control_models import CommitID

log = logging.getLogger(__name__)


# SEE OAS
#
#  https://github.com/ITISFoundation/osparc-simcore/blob/master/services/web/server/src/simcore_service_webserver/api/v0/openapi.yaml#L8563
#
URL_PATTERN = re.compile(rf"^\/{VTAG}\/projects\/({UUID_RE})[\/.]{1}")


@web.middleware
async def projects_redirection_middleware(request: web.Request, handler: _Handler):
    """Intercepts /project/{project_id}* requests and redirect them to the copy @HEAD"""

    if match := URL_PATTERN.match(str(request.rel_url)):
        assert match.group(1) == request.match_info["project_id"]  # nosec

        project_id = ProjectID(request.match_info["project_id"])

        vc_repo = VersionControlForMetaModeling(request)
        if repo_id := await vc_repo.get_repo_id(project_id):
            # Changes resolved project_id parameter with working copy instead
            #
            # TODO: optimize db calls
            wcopy_project_id = await vc_repo.get_wcopy_project_id(repo_id)
            request.match_info["project_id"] = str(wcopy_project_id)

            if wcopy_project_id != project_id:
                request[RQ_REQUESTED_REPO_PROJECT_UUID_KEY] = wcopy_project_id
                log.debug(
                    "Redirecting project '%s' to working copy '%s'",
                    project_id,
                    wcopy_project_id,
                )

    response = await handler(request)

    # TODO: A solution would be to have project/*/workbench  instead?

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
