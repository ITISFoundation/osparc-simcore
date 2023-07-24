""" web-api handler functions added by the meta app's module

"""
import logging
from collections.abc import Callable
from typing import NamedTuple

from aiohttp import web
from models_library.projects import ProjectID
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    Page,
)
from models_library.rest_pagination_utils import paginate_data
from pydantic import BaseModel, ValidationError, validator
from pydantic.fields import Field
from pydantic.networks import HttpUrl
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._meta import api_version_prefix as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import create_url_for_function, envelope_json_response
from ..version_control.models import CheckpointID, CommitID, TagProxy
from ..version_control.vc_tags import parse_workcopy_project_tag_name
from ._iterations import IterationID, ProjectIteration
from ._results import ExtractedResults, extract_project_results
from ._version_control import VersionControlForMetaModeling

log = logging.getLogger(__name__)

# HANDLER'S CORE IMPLEMENTATION ------------------------------------------------------------


class _QueryParametersModel(BaseModel):
    project_uuid: ProjectID
    ref_id: CommitID
    limit: int = Field(
        DEFAULT_NUMBER_OF_ITEMS_PER_PAGE, gt=0, lt=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
    )
    offset: int = 0

    @validator("ref_id", pre=True)
    @classmethod
    def tags_as_refid_not_implemented(cls, v):
        try:
            return CommitID(v)
        except ValueError as err:
            # e.g. HEAD
            msg = "cannot convert ref (e.g. HEAD) -> commit id"
            raise NotImplementedError(msg) from err


def parse_query_parameters(request: web.Request) -> _QueryParametersModel:
    try:
        return _QueryParametersModel(**request.match_info)
    except ValidationError as err:
        raise web.HTTPUnprocessableEntity(
            reason=f"Invalid query parameters: {err}"
        ) from err


class _NotTaggedAsIteration(Exception):
    """A commit does not contain the tags
    to be identified as an iterator
    """


class IterationItem(NamedTuple):
    project_id: ProjectID
    commit_id: CommitID
    iteration_index: IterationID


class _IterationsRange(NamedTuple):
    items: list[IterationItem]
    total_count: int


async def _get_project_iterations_range(
    vc_repo: VersionControlForMetaModeling,
    project_uuid: ProjectID,
    commit_id: CommitID,
    offset: int = 0,
    limit: int | None = None,
) -> _IterationsRange:
    assert offset >= 0  # nosec

    repo_id = await vc_repo.get_repo_id(project_uuid)
    assert repo_id is not None

    total_number_of_iterations = 0

    # Searches all subsequent commits (i.e. children) and retrieve their tags
    tags_per_child: list[list[TagProxy]] = await vc_repo.get_children_tags(
        repo_id, commit_id
    )

    iter_items: list[IterationItem] = []
    for n, tags in enumerate(tags_per_child):
        try:
            iteration: ProjectIteration | None = None
            workcopy_id: ProjectID | None = None

            for tag in tags:
                if pim := ProjectIteration.from_tag_name(
                    tag.name, return_none_if_fails=True
                ):
                    if iteration:
                        msg = f"This commit_id={commit_id!r} has more than one iteration tag={tag!r}"
                        raise _NotTaggedAsIteration(msg)
                    iteration = pim
                elif pid := parse_workcopy_project_tag_name(tag.name):
                    if workcopy_id:
                        msg = f"This commit_id={commit_id!r} has more than one workcopy  tag={tag!r}"
                        raise _NotTaggedAsIteration(msg)
                    workcopy_id = pid
                else:
                    log.debug("Got %s for children of %s", f"{tag=}", f"{commit_id=}")

            if not workcopy_id:
                msg = f"No workcopy tag found in tags={tags!r}"
                raise _NotTaggedAsIteration(msg)
            if not iteration:
                msg = f"No iteration tag found in tags={tags!r}"
                raise _NotTaggedAsIteration(msg)

            iter_items.append(
                IterationItem(
                    project_id=workcopy_id,
                    commit_id=iteration.repo_commit_id,
                    iteration_index=iteration.iteration_index,
                )
            )

        except _NotTaggedAsIteration as err:
            log.warning(
                "Skipping %d-th child since is not tagged as an iteration of %s/%s: %s",
                n,
                f"{repo_id=}",
                f"{commit_id=}",
                f"{err=}",
            )

    # Selects range on those tagged as iterations and returned their assigned workcopy id
    total_number_of_iterations = len(iter_items)

    # sort and select. If requested interval is outside of range, it returns empty
    iter_items.sort(key=lambda item: item.iteration_index)

    if limit is None:
        return _IterationsRange(
            items=iter_items[offset:],
            total_count=total_number_of_iterations,
        )

    return _IterationsRange(
        items=iter_items[offset : (offset + limit)],
        total_count=total_number_of_iterations,
    )


async def create_or_get_project_iterations(
    vc_repo: VersionControlForMetaModeling,
    project_uuid: ProjectID,
    commit_id: CommitID,
) -> list[IterationItem]:
    raise NotImplementedError


# MODELS ------------------------------------------------------------


class ParentMetaProjectRef(BaseModel):
    project_id: ProjectID
    ref_id: CheckpointID


class _BaseModelGet(BaseModel):
    name: str = Field(..., description="Iteration's resource API name")
    parent: ParentMetaProjectRef = Field(
        ..., description="Reference to the the meta-project that created this iteration"
    )

    url: HttpUrl = Field(..., description="self reference")


class ProjectIterationItem(_BaseModelGet):
    iteration_index: IterationID = Field(...)

    workcopy_project_id: ProjectID = Field(
        ...,
        description="ID to this iteration's working copy."
        "A working copy is a real project where this iteration is run",
    )

    workcopy_project_url: HttpUrl = Field(
        ..., description="reference to a working copy project"
    )

    @classmethod
    def create_iteration(
        cls,
        meta_project_uuid,
        meta_project_commit_id,
        iteration_index,
        project_id,
        url_for: Callable,
    ):
        return cls(
            name=f"projects/{meta_project_uuid}/checkpoint/{meta_project_commit_id}/iterations/{iteration_index}",
            parent=ParentMetaProjectRef(
                project_id=meta_project_uuid, ref_id=meta_project_commit_id
            ),
            iteration_index=iteration_index,
            workcopy_project_id=project_id,
            workcopy_project_url=url_for(
                "get_project",
                project_id=project_id,
            ),
            url=url_for(
                f"{__name__}._get_meta_project_iterations_handler",
                project_uuid=meta_project_uuid,
                ref_id=meta_project_commit_id,
                iter_id=iteration_index,
            ),
        )


class ProjectIterationResultItem(ProjectIterationItem):
    results: ExtractedResults

    @classmethod
    def create_result(  # pylint: disable=arguments-differ
        cls,
        meta_project_uuid,
        meta_project_commit_id,
        iteration_index,
        project_id,
        results,
        url_for: Callable,
    ):
        return cls(
            name=f"projects/{meta_project_uuid}/checkpoint/{meta_project_commit_id}/iterations/{iteration_index}/results",
            parent=ParentMetaProjectRef(
                project_id=meta_project_uuid, ref_id=meta_project_commit_id
            ),
            iteration_index=iteration_index,
            workcopy_project_id=project_id,
            results=results,
            workcopy_project_url=url_for(
                "get_project",
                project_id=project_id,
            ),
            url=url_for(
                f"{__name__}._get_meta_project_iteration_results_handler",
                project_uuid=meta_project_uuid,
                ref_id=meta_project_commit_id,
                iter_id=iteration_index,
            ),
        )


# ROUTES ------------------------------------------------------------

routes = web.RouteTableDef()


@routes.get(
    f"/{VTAG}/projects/{{project_uuid}}/checkpoint/{{ref_id}}/iterations",
    name=f"{__name__}._list_meta_project_iterations_handler",
)
@login_required
@permission_required("project.snapshot.read")
async def _list_meta_project_iterations_handler(request: web.Request) -> web.Response:
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/2735

    # parse and validate request ----
    q = parse_query_parameters(request)
    meta_project_uuid = q.project_uuid
    meta_project_commit_id = q.ref_id

    url_for = create_url_for_function(request)
    vc_repo = VersionControlForMetaModeling(request)

    # core function ----
    iterations_range = await _get_project_iterations_range(
        vc_repo,
        meta_project_uuid,
        meta_project_commit_id,
        offset=q.offset,
        limit=q.limit,
    )

    if iterations_range.total_count == 0:
        raise web.HTTPNotFound(
            reason=f"No iterations found for project {meta_project_uuid=}/{meta_project_commit_id=}"
        )

    assert len(iterations_range.items) <= q.limit  # nosec

    # parse and validate response ----
    page_items = [
        ProjectIterationItem.create_iteration(
            meta_project_uuid,
            meta_project_commit_id,
            item.iteration_index,
            item.project_id,
            url_for,
        )
        for item in iterations_range.items
    ]

    page = Page[ProjectIterationItem].parse_obj(
        paginate_data(
            chunk=page_items,
            request_url=request.url,
            total=iterations_range.total_count,
            limit=q.limit,
            offset=q.offset,
        )
    )
    return web.Response(
        text=page.json(**RESPONSE_MODEL_POLICY),
        content_type="application/json",
    )


# NOTE: Enable when create_or_get_project_iterations is implemented
# SEE https://github.com/ITISFoundation/osparc-simcore/issues/2735
#
# @routes.post(
@permission_required("project.snapshot.create")
async def _create_meta_project_iterations_handler(request: web.Request) -> web.Response:
    q = parse_query_parameters(request)
    meta_project_uuid = q.project_uuid
    meta_project_commit_id = q.ref_id

    url_for = create_url_for_function(request)
    vc_repo = VersionControlForMetaModeling(request)

    # core function ----
    project_iterations = await create_or_get_project_iterations(
        vc_repo, meta_project_uuid, meta_project_commit_id
    )

    # parse and validate response ----
    iterations_items = [
        ProjectIterationItem.create_iteration(
            meta_project_uuid,
            meta_project_commit_id,
            item.iteration_index,
            item.project_id,
            url_for,
        )
        for item in project_iterations
    ]

    return envelope_json_response(iterations_items, web.HTTPCreated)


@routes.get(
    f"/{VTAG}/projects/{{project_uuid}}/checkpoint/{{ref_id}}/iterations/{{iter_id}}",
    name=f"{__name__}._get_meta_project_iterations_handler",
)
@login_required
@permission_required("project.snapshot.read")
async def _get_meta_project_iterations_handler(request: web.Request) -> web.Response:
    msg = "Currently iteration is retrieved via GET /projects/{workcopy_project_id}SEE https://github.com/ITISFoundation/osparc-simcore/issues/2735"
    raise NotImplementedError(msg)


@routes.get(
    f"/{VTAG}/projects/{{project_uuid}}/checkpoint/{{ref_id}}/iterations/-/results",
    name=f"{__name__}._list_meta_project_iterations_results_handler",
)
@login_required
@permission_required("project.snapshot.read")
async def _list_meta_project_iterations_results_handler(
    request: web.Request,
) -> web.Response:
    # parse and validate request ----
    q = parse_query_parameters(request)
    meta_project_uuid = q.project_uuid
    meta_project_commit_id = q.ref_id

    url_for = create_url_for_function(request)
    vc_repo = VersionControlForMetaModeling(request)

    # core function ----
    iterations_range = await _get_project_iterations_range(
        vc_repo,
        meta_project_uuid,
        meta_project_commit_id,
        offset=q.offset,
        limit=q.limit,
    )

    if iterations_range.total_count == 0:
        raise web.HTTPNotFound(
            reason=f"No iterations found for projects/{meta_project_uuid}/checkpoint/{meta_project_commit_id}"
        )

    assert len(iterations_range.items) <= q.limit  # nosec

    # get every project from the database and extract results
    _prj_data = {}
    for item in iterations_range.items:
        prj = await vc_repo.get_project(f"{item.project_id}", include=["workbench"])
        _prj_data[item.project_id] = prj["workbench"]

    def _get_project_results(project_id) -> ExtractedResults:
        return extract_project_results(_prj_data[project_id])

    # parse and validate response ----
    page_items = [
        ProjectIterationResultItem.create_result(
            meta_project_uuid,
            meta_project_commit_id,
            item.iteration_index,
            item.project_id,
            _get_project_results(item.project_id),
            url_for,
        )
        for item in iterations_range.items
    ]

    page = Page[ProjectIterationResultItem].parse_obj(
        paginate_data(
            chunk=page_items,
            request_url=request.url,
            total=iterations_range.total_count,
            limit=q.limit,
            offset=q.offset,
        )
    )
    return web.Response(
        text=page.json(**RESPONSE_MODEL_POLICY),
        content_type="application/json",
    )


@routes.get(
    f"/{VTAG}/projects/{{project_uuid}}/checkpoint/{{ref_id}}/iterations/{{iter_id}}/results",
    name=f"{__name__}._get_meta_project_iteration_results_handler",
)
@login_required
@permission_required("project.snapshot.read")
async def _get_meta_project_iteration_results_handler(
    request: web.Request,
) -> web.Response:
    msg = "SEE https://github.com/ITISFoundation/osparc-simcore/issues/2735"
    raise NotImplementedError(msg)
