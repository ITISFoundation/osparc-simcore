""" web-api handler functions added by the meta app's module

"""
import logging
from typing import Any, Dict, List, Tuple, Union

from aiohttp import web
from models_library.projects import ProjectID
from pydantic import BaseModel
from pydantic.fields import Field
from pydantic.networks import HttpUrl
from servicelib.rest_pagination_utils import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageResponseLimitOffset,
)

from ._meta import api_version_prefix as VTAG
from .meta_iterations import IterInfoDict, parse_iteration_tag_name
from .rest_utils import RESPONSE_MODEL_POLICY
from .utils_aiohttp import create_url_for_function
from .version_control_db import VersionControlForMetaModeling
from .version_control_models import CheckpointID, CommitID, RefID, TagProxy
from .version_control_tags import compose_wcopy_project_id, parse_wcopy_project_tag_name

# MODELS ------------------------------------------------------------


class MetaProjectIDs(BaseModel):
    project_id: ProjectID
    checkpoint_id: CheckpointID


class ProjectIterationAsItem(BaseModel):
    name: str = Field(
        ...,
        description="Iteration's resource name [AIP-122](https://google.aip.dev/122)",
    )
    parent: MetaProjectIDs = Field(
        ..., description="Identifies the meta-project that created this iteration"
    )

    wcopy_project_id: ProjectID = Field(
        ...,
        description="ID to this iteration's working copy."
        "A working copy is a real project where this iteration is run",
    )

    wcopy_project_url: HttpUrl  # should be read-only!
    url: HttpUrl  # self


# ROUTES ------------------------------------------------------------
routes = web.RouteTableDef()


@routes.get(
    f"/{VTAG}/meta/projects/{{project_uuid}}/checkpoint/{{ref_id}}/iterations",
    name="{__name__}._list_meta_project_iterations_handler",
)
async def _list_meta_project_iterations_handler(request: web.Request) -> web.Response:

    # FIXME: check access to non owned projects user_id = request[RQT_USERID_KEY]
    url_for = create_url_for_function(request)
    vc_repo = VersionControlForMetaModeling(request)

    _project_uuid = ProjectID(request.match_info["project_uuid"])
    _ref_id = request.match_info["ref_id"]

    _limit = int(request.query.get("limit", DEFAULT_NUMBER_OF_ITEMS_PER_PAGE))
    _offset = int(request.query.get("offset", 0))

    try:
        commit_id = CommitID(_ref_id)
    except ValueError:
        # e.g. HEAD
        raise NotImplementedError("cannot convert ref (e.g. HEAD) -> commit id")

    (
        wcopy_projects_ids,
        total_number_of_iterations,
    ) = await list_wcopy_projects_iterations(
        vc_repo, _project_uuid, commit_id, offset=_offset, limit=_limit
    )

    assert len(wcopy_projects_ids) <= _limit  # nosec

    # parse and validate
    iterations_list = [
        ProjectIterationAsItem.parse_obj(
            {
                "parent": MetaProjectIDs(project_id=_project_uuid, ref_id=commit_id),
                "wcopy_project_id": wcp_id,
                "wcopy_project_url": url_for(
                    "get_project",
                    project_uuid=wcp_id,
                ),
                "url": url_for(
                    f"{__name__}._list_meta_project_iterations_handler",
                    project_uuid=_project_uuid,
                ),
            }
        )
        for wcp_id in wcopy_projects_ids
    ]

    return web.Response(
        text=PageResponseLimitOffset.paginate_data(
            data=iterations_list,
            request_url=request.url,
            total=total_number_of_iterations,
            limit=_limit,
            offset=_offset,
        ).json(**RESPONSE_MODEL_POLICY),
        content_type="application/json",
    )


logger = logging.getLogger(__name__)


async def list_wcopy_projects_iterations(
    vc_repo: VersionControlForMetaModeling,
    project_uuid: ProjectID,
    commit_id: CommitID,
    offset: int,
    limit: int,
) -> Tuple[List[ProjectID], int]:

    repo_id = await vc_repo.get_repo_id(project_uuid)
    assert repo_id is not None

    # search iterations
    #  - check all commits with parent_commit == ref_id, are branch

    tags_per_child: List[List[TagProxy]] = await vc_repo.get_children_tags(
        repo_id, commit_id
    )

    iterations: List[IterInfoDict] = []
    for tags in tags_per_child:
        for tag in tags:
            if iterinfo := parse_iteration_tag_name(tag.message):
                assert int(iterinfo.repo_commit_id) == commit_id
                iterations.append(iterinfo)
            elif iterinfo := parse_wcopy_project_tag_name(tag.message):
                pass
            else:
                logger.debug("Got tag: %s for children of {}", tag)

    # wcopy_project_id = compose_wcopy_project_id(repo.project_uuid, commit_id)

    wcopy_project_id = await vc_repo.get_wcopy_project_id(repo_id, commit_id)

    # build project_ids based on
    raise NotImplementedError
