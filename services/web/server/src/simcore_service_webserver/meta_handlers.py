""" web-api handler functions added by the meta app's module

"""
import logging
from typing import List, Optional, Tuple

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
from .meta_db import VersionControlForMetaModeling
from .meta_iterations import ProjectIteration
from .rest_utils import RESPONSE_MODEL_POLICY
from .utils_aiohttp import create_url_for_function, envelope_json_response

from .version_control_models import CheckpointID, CommitID, TagProxy
from .version_control_tags import parse_wcopy_project_tag_name

log = logging.getLogger(__name__)


# HANDLER'S CORE ------------------------------------------------------------

IterationTuple = Tuple[ProjectID, CommitID]


async def list_project_iterations(
    vc_repo: VersionControlForMetaModeling,
    project_uuid: ProjectID,
    commit_id: CommitID,
    offset: int = 0,
    limit: Optional[int] = None,
) -> Tuple[List[IterationTuple], int]:

    assert offset >= 0  # nosec

    repo_id = await vc_repo.get_repo_id(project_uuid)
    assert repo_id is not None

    total_number_of_iterations = 0  # count number of iterations

    # Search all subsequent commits (i.e. children) and retrieve their tags
    # Select range on those tagged as iterations and returned their assigned wcopy id
    # Can also check all associated project uuids and see if they exists
    # FIXME: do all these operations in database
    tags_per_child: List[List[TagProxy]] = await vc_repo.get_children_tags(
        repo_id, commit_id
    )

    iterations: List[Tuple[ProjectID, CommitID]] = []
    for n, tags in enumerate(tags_per_child):

        # FIXME: the db query did not guarantee
        # not sorted
        # not limited
        # not certain if tags we need
        try:
            iteration: Optional[ProjectIteration] = None
            wcopy_id: Optional[ProjectID] = None

            for tag in tags:
                if pim := ProjectIteration.from_tag_name(
                    tag.name, return_none_if_fails=True
                ):
                    if iteration:
                        raise ValueError(
                            f"This entry has more than one iteration {tag=}"
                        )
                    iteration = pim
                elif pid := parse_wcopy_project_tag_name(tag.name):
                    if wcopy_id:
                        raise ValueError(f"This entry has more than one wcopy  {tag=}")
                    wcopy_id = pid
                else:
                    log.debug("Got %s for children of %s", f"{tag=}", f"{commit_id=}")

            if not wcopy_id:
                raise ValueError("No working copy found")
            if not iteration:
                raise ValueError("No iteration tag found")

            total_number_of_iterations = max(
                total_number_of_iterations, iteration.total_count
            )
            iterations.append((wcopy_id, iteration.iter_index))

        except ValueError as err:
            log.debug("Skipping child %s: %s", n, err)

    total_number_of_iterations = len(iterations)

    # sort and select. If requested interval is outside of range, it returns empty
    iterations.sort(key=lambda tup: tup[1])

    if limit is None:
        return iterations[offset:], total_number_of_iterations

    return iterations[offset : (offset + limit)], total_number_of_iterations


async def create_or_get_project_iterations(
    vc_repo: VersionControlForMetaModeling,
    project_uuid: ProjectID,
    commit_id: CommitID,
) -> List[IterationTuple]:

    raise NotImplementedError()


# MODELS ------------------------------------------------------------


class ParentMetaProjectRef(BaseModel):
    project_id: ProjectID
    ref_id: CheckpointID


class ProjectIterationAsItem(BaseModel):
    name: str = Field(
        ...,
        description="Iteration's resource name [AIP-122](https://google.aip.dev/122)",
    )
    parent: ParentMetaProjectRef = Field(
        ..., description="Reference to the the meta-project that created this iteration"
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
    f"/{VTAG}/projects/{{project_uuid}}/checkpoint/{{ref_id}}/iterations",
    name=f"{__name__}._list_meta_project_iterations_handler",
)
async def _list_meta_project_iterations_handler(request: web.Request) -> web.Response:
    # FIXME: check access to non owned projects user_id = request[RQT_USERID_KEY]

    # parse and validate request ----
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

    # core function ----
    (
        selected_project_iterations,
        total_number_of_iterations,
    ) = await list_project_iterations(
        vc_repo, _project_uuid, commit_id, offset=_offset, limit=_limit
    )

    if total_number_of_iterations == 0:
        raise web.HTTPNotFound(
            reason=f"No iterations found for project {_project_uuid=}/{commit_id=}"
        )

    assert len(selected_project_iterations) <= _limit  # nosec

    # parse and validate response ----
    iterations_items = [
        ProjectIterationAsItem(
            name=f"projects/{_project_uuid}/checkpoint/{commit_id}/iterations/{iter_id}",
            parent=ParentMetaProjectRef(project_id=_project_uuid, ref_id=commit_id),
            wcopy_project_id=wcp_id,
            wcopy_project_url=url_for(
                "get_project",
                project_id=wcp_id,
            ),
            url=url_for(
                f"{__name__}._list_meta_project_iterations_handler",
                project_uuid=_project_uuid,
                ref_id=commit_id,
            ),
        )
        for wcp_id, iter_id in selected_project_iterations
    ]

    return web.Response(
        text=PageResponseLimitOffset.paginate_data(
            data=iterations_items,
            request_url=request.url,
            total=total_number_of_iterations,
            limit=_limit,
            offset=_offset,
        ).json(**RESPONSE_MODEL_POLICY),
        content_type="application/json",
    )


@routes.post(
    f"/{VTAG}/projects/{{project_uuid}}/checkpoint/{{ref_id}}/iterations",
    name=f"{__name__}._create_meta_project_iterations_handler",
)
async def _create_meta_project_iterations_handler(request: web.Request) -> web.Response:
    # FIXME: check access to non owned projects user_id = request[RQT_USERID_KEY]
    url_for = create_url_for_function(request)
    vc_repo = VersionControlForMetaModeling(request)

    _project_uuid = ProjectID(request.match_info["project_uuid"])
    _ref_id = request.match_info["ref_id"]
    try:
        commit_id = CommitID(_ref_id)
    except ValueError:
        # e.g. HEAD
        raise NotImplementedError("cannot convert ref (e.g. HEAD) -> commit id")

    # core function ----
    project_iterations = await create_or_get_project_iterations(
        vc_repo, _project_uuid, commit_id
    )

    # parse and validate response ----
    iterations_items = [
        ProjectIterationAsItem(
            name=f"projects/{_project_uuid}/checkpoint/{commit_id}/iterations/{iter_id}",
            parent=ParentMetaProjectRef(project_id=_project_uuid, ref_id=commit_id),
            wcopy_project_id=wcp_id,
            wcopy_project_url=url_for(
                "get_project",
                project_id=wcp_id,
            ),
            url=url_for(
                f"{__name__}._create_meta_project_iterations_handler",
                project_uuid=_project_uuid,
                ref_id=commit_id,
            ),
        )
        for wcp_id, iter_id in project_iterations
    ]

    return envelope_json_response(iterations_items, web.HTTPCreated)


# TODO:
# @routes.get(
#     f"/{VTAG}/projects/{{project_uuid}}/checkpoint/{{ref_id}}/iterations/{{iter_id}}",
#     name=f"{__name__}._get_meta_project_iterations_handler",
# )
# async def _get_meta_project_iterations_handler(request: web.Request) -> web.Response:
#     raise NotImplementedError
