"""REST controller for the study-dispatch endpoint.

POST /{API_VTAG}/studies/{study_id}:dispatch

Starts an LRT that clones a published study into the authenticated user's account.
Returns 202 + TaskGet so the SPA can poll for progress.
"""

import logging

from aiohttp import web
from servicelib.aiohttp import status as http_status
from servicelib.aiohttp.long_running_tasks.server import start_long_running_task

from ...._meta import API_VTAG
from ....login.decorators import login_required
from ....models import AuthenticatedRequestContext
from ....security.decorators import permission_required
from ....utils_aiohttp import get_api_base_url
from ....web_requests_validation import parse_request_path_parameters_as
from ..._dispatch_task import dispatch_study
from ..._guards import check_studies_dispatcher_enabled
from ..._studies_access import RedirectToFrontEndPageError, _get_published_template_project
from .study_dispatch_schemas import StudyDispatchPathParams

_logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


@routes.post(f"/{API_VTAG}/studies/{{study_id}}:dispatch", name="dispatch_study")
@login_required
@permission_required("study.dispatch")
async def dispatch_study_handler(request: web.Request) -> web.StreamResponse:
    """Start an async clone of a published study into the requesting user's account.

    Returns 202 Accepted + TaskGet for polling via ``/{API_VTAG}/tasks-legacy/{task_id}``.
    """
    check_studies_dispatcher_enabled(request)

    path_params = parse_request_path_parameters_as(StudyDispatchPathParams, request)
    study_id = f"{path_params.study_id}"
    req_ctx = AuthenticatedRequestContext.model_validate(request)

    # Pre-flight: validate accessibility synchronously so the SPA gets an immediate 4xx
    # for inaccessible / non-published studies instead of a 202 that fails later in the task.
    try:
        await _get_published_template_project(
            request,
            study_id,
            is_user_authenticated=True,  # user is always authenticated here (login_required)
        )
    except RedirectToFrontEndPageError as exc:
        if exc.status_code == http_status.HTTP_404_NOT_FOUND:
            raise web.HTTPNotFound(reason=f"Study {study_id!r} not found or not accessible") from exc
        raise web.HTTPForbidden(reason=f"Access denied to study {study_id!r}") from exc

    return await start_long_running_task(
        request,
        dispatch_study.__name__,
        fire_and_forget=True,
        task_context=req_ctx.model_dump(mode="json", by_alias=True),
        # task arguments
        study_id=study_id,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        template_parameters=dict(request.query),
        product_api_base_url=get_api_base_url(request),
    )
