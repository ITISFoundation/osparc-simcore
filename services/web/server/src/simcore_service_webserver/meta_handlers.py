""" web-api handler functions added by the meta app's module

"""
import logging
from typing import List, NamedTuple, Optional, Tuple

from aiohttp import web
from models_library.projects import ProjectID
from models_library.rest_pagination import DEFAULT_NUMBER_OF_ITEMS_PER_PAGE, Page
from models_library.rest_pagination_utils import paginate_data
from pydantic import BaseModel
from pydantic.fields import Field
from pydantic.networks import HttpUrl

from ._meta import api_version_prefix as VTAG
from .meta_iterations import ProjectIteration
from .meta_version_control import VersionControlForMetaModeling
from .rest_utils import RESPONSE_MODEL_POLICY
from .security_decorators import permission_required
from .utils_aiohttp import create_url_for_function, envelope_json_response
from .version_control_models import CheckpointID, CommitID, TagProxy
from .version_control_tags import parse_workcopy_project_tag_name

log = logging.getLogger(__name__)


# HANDLER'S CORE IMPLEMENTATION ------------------------------------------------------------

IterationTuple = Tuple[ProjectID, CommitID]


class _TagInfoError(Exception):
    """Local error related with the information
    (workcopy or iteration) embedded in a vc tag"""

    ...


class _IterationsRange(NamedTuple):
    items: List[IterationTuple]
    total_count: int


async def _get_project_iterations_range(
    vc_repo: VersionControlForMetaModeling,
    project_uuid: ProjectID,
    commit_id: CommitID,
    offset: int = 0,
    limit: Optional[int] = None,
) -> _IterationsRange:
    assert offset >= 0  # nosec

    repo_id = await vc_repo.get_repo_id(project_uuid)
    assert repo_id is not None

    total_number_of_iterations = 0

    # Searches all subsequent commits (i.e. children) and retrieve their tags
    # FIXME: do all these operations in database.
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
            workcopy_id: Optional[ProjectID] = None

            for tag in tags:
                if pim := ProjectIteration.from_tag_name(
                    tag.name, return_none_if_fails=True
                ):
                    if iteration:
                        raise _TagInfoError(
                            f"This entry has more than one iteration {tag=}"
                        )
                    iteration = pim
                elif pid := parse_workcopy_project_tag_name(tag.name):
                    if workcopy_id:
                        raise _TagInfoError(
                            f"This entry has more than one workcopy  {tag=}"
                        )
                    workcopy_id = pid
                else:
                    log.debug("Got %s for children of %s", f"{tag=}", f"{commit_id=}")

            if not workcopy_id:
                raise _TagInfoError(f"No workcopy tag found in {tags=}")
            if not iteration:
                raise _TagInfoError(f"No iteration tag found in {tags=}")

            iterations.append((workcopy_id, iteration.iter_index))

        except _TagInfoError as err:
            log.warning(
                "Skipping %d-th child due to a wrong/inconsistent tag: %s", n, err
            )

    # Selects range on those tagged as iterations and returned their assigned workcopy id
    total_number_of_iterations = len(iterations)

    # sort and select. If requested interval is outside of range, it returns empty
    iterations.sort(key=lambda tup: tup[1])

    if limit is None:
        return _IterationsRange(
            items=iterations[offset:], total_count=total_number_of_iterations
        )

    return _IterationsRange(
        items=iterations[offset : (offset + limit)],
        total_count=total_number_of_iterations,
    )


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

    workcopy_project_id: ProjectID = Field(
        ...,
        description="ID to this iteration's working copy."
        "A working copy is a real project where this iteration is run",
    )

    workcopy_project_url: HttpUrl = Field(
        ..., description="reference to a working copy project"
    )
    url: HttpUrl = Field(..., description="self reference")


# ROUTES ------------------------------------------------------------


routes = web.RouteTableDef()


@routes.get(
    f"/{VTAG}/projects/{{project_uuid}}/checkpoint/{{ref_id}}/iterations",
    name=f"{__name__}._list_meta_project_iterations_handler",
)
@permission_required("project.snapshot.read")
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
    except ValueError as err:
        # e.g. HEAD
        raise NotImplementedError(
            "cannot convert ref (e.g. HEAD) -> commit id"
        ) from err

    # core function ----
    iterations = await _get_project_iterations_range(
        vc_repo, _project_uuid, commit_id, offset=_offset, limit=_limit
    )

    if iterations.total_count == 0:
        raise web.HTTPNotFound(
            reason=f"No iterations found for project {_project_uuid=}/{commit_id=}"
        )

    assert len(iterations.items) <= _limit  # nosec

    # parse and validate response ----
    page_items = [
        ProjectIterationAsItem(
            name=f"projects/{_project_uuid}/checkpoint/{commit_id}/iterations/{iter_id}",
            parent=ParentMetaProjectRef(project_id=_project_uuid, ref_id=commit_id),
            workcopy_project_id=wcp_id,
            workcopy_project_url=url_for(
                "get_project",
                project_id=wcp_id,
            ),
            url=url_for(
                f"{__name__}._list_meta_project_iterations_handler",
                project_uuid=_project_uuid,
                ref_id=commit_id,
            ),
        )
        for wcp_id, iter_id in iterations.items
    ]

    page = Page[ProjectIterationAsItem].parse_obj(
        paginate_data(
            chunk=page_items,
            request_url=request.url,
            total=iterations.total_count,
            limit=_limit,
            offset=_offset,
        )
    )
    return web.Response(
        text=page.json(**RESPONSE_MODEL_POLICY),
        content_type="application/json",
    )


# TODO: Enable when create_or_get_project_iterations is implemented
# @routes.post(
#    f"/{VTAG}/projects/{{project_uuid}}/checkpoint/{{ref_id}}/iterations",
#    name=f"{__name__}._create_meta_project_iterations_handler",
# )
@permission_required("project.snapshot.create")
async def _create_meta_project_iterations_handler(request: web.Request) -> web.Response:
    # FIXME: check access to non owned projects user_id = request[RQT_USERID_KEY]
    url_for = create_url_for_function(request)
    vc_repo = VersionControlForMetaModeling(request)

    _project_uuid = ProjectID(request.match_info["project_uuid"])
    _ref_id = request.match_info["ref_id"]
    try:
        commit_id = CommitID(_ref_id)
    except ValueError as err:
        # e.g. HEAD
        raise NotImplementedError(
            "cannot convert ref (e.g. HEAD) -> commit id"
        ) from err

    # core function ----
    project_iterations = await create_or_get_project_iterations(
        vc_repo, _project_uuid, commit_id
    )

    # parse and validate response ----
    iterations_items = [
        ProjectIterationAsItem(
            name=f"projects/{_project_uuid}/checkpoint/{commit_id}/iterations/{iter_id}",
            parent=ParentMetaProjectRef(project_id=_project_uuid, ref_id=commit_id),
            workcopy_project_id=wcp_id,
            workcopy_project_url=url_for(
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


# TODO: registry as route when implemented. Currently iteration is retrieved via GET /projects/{workcopy_project_id}
# @routes.get(
#     f"/{VTAG}/projects/{{project_uuid}}/checkpoint/{{ref_id}}/iterations/{{iter_id}}",
#     name=f"{__name__}._get_meta_project_iterations_handler",
# )
async def _get_meta_project_iterations_handler(request: web.Request) -> web.Response:
    raise NotImplementedError
