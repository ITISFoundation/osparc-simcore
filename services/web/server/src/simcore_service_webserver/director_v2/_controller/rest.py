import asyncio
import logging
from typing import Any

from aiohttp import web
from models_library.api_schemas_webserver.computations import (
    ComputationGet,
    ComputationPathParams,
    ComputationStart,
    ComputationStarted,
)
from models_library.projects import CommitID, ProjectID
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.common_headers import (
    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    X_SIMCORE_USER_AGENT,
)
from servicelib.request_keys import RQT_USERID_KEY

from ..._meta import API_VTAG as VTAG
from ...login.decorators import login_required
from ...models import RequestContext
from ...products import products_web
from ...security.decorators import permission_required
from ...utils_aiohttp import envelope_json_response
from .. import _director_v2_service
from .._client import DirectorV2RestClient
from .._director_v2_abc_service import get_project_run_policy
from ._rest_exceptions import handle_rest_requests_exceptions

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.post(f"/{VTAG}/computations/{{project_id}}:start", name="start_computation")
@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
@handle_rest_requests_exceptions
async def start_computation(request: web.Request) -> web.Response:
    simcore_user_agent = request.headers.get(
        X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
    )
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ComputationPathParams, request)

    subgraph: set[str] = set()
    force_restart: bool = False  # NOTE: deprecate this entry
    if request.can_read_body:
        body_params = await parse_request_body_as(ComputationStart, request)
        subgraph = body_params.subgraph
        force_restart = body_params.force_restart

    # Group properties
    group_properties = await _director_v2_service.get_group_properties(
        request.app, product_name=req_ctx.product_name, user_id=req_ctx.user_id
    )

    # Get wallet information
    product = products_web.get_current_product(request)
    wallet_info = await _director_v2_service.get_wallet_info(
        request.app,
        product=product,
        user_id=req_ctx.user_id,
        project_id=path_params.project_id,
        product_name=req_ctx.product_name,
    )

    options = {
        "start_pipeline": True,
        "subgraph": list(subgraph),  # sets are not natively json serializable
        "force_restart": force_restart,
        "simcore_user_agent": simcore_user_agent,
        "use_on_demand_clusters": group_properties.use_on_demand_clusters,
        "wallet_info": wallet_info,
    }

    run_policy = get_project_run_policy(request.app)
    assert run_policy  # nosec

    running_project_ids: list[ProjectID]
    project_vc_commits: list[CommitID]

    (
        running_project_ids,
        project_vc_commits,
    ) = await run_policy.get_or_create_runnable_projects(
        request, path_params.project_id
    )
    _logger.debug(
        "Project %s will start %d variants: %s",
        f"{path_params.project_id=}",
        len(running_project_ids),
        f"{running_project_ids=}",
    )

    assert running_project_ids  # nosec
    assert (  # nosec
        len(running_project_ids) == len(project_vc_commits)
        if project_vc_commits
        else True
    )

    computations = DirectorV2RestClient(request.app)
    _started_pipelines_ids = await asyncio.gather(
        *[
            computations.start_computation(
                pid, req_ctx.user_id, req_ctx.product_name, **options
            )
            for pid in running_project_ids
        ]
    )

    assert set(_started_pipelines_ids) == set(map(str, running_project_ids))  # nosec

    data: dict[str, Any] = {
        "pipeline_id": path_params.project_id,
    }
    if project_vc_commits:
        data["ref_ids"] = project_vc_commits

    return envelope_json_response(
        ComputationStarted.model_validate(data), status_cls=web.HTTPCreated
    )


@routes.post(f"/{VTAG}/computations/{{project_id}}:stop", name="stop_computation")
@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
@handle_rest_requests_exceptions
async def stop_computation(request: web.Request) -> web.Response:
    req_ctx = RequestContext.model_validate(request)
    computations = DirectorV2RestClient(request.app)
    run_policy = get_project_run_policy(request.app)
    assert run_policy  # nosec

    path_params = parse_request_path_parameters_as(ComputationPathParams, request)

    project_ids = await run_policy.get_runnable_projects_ids(
        request, path_params.project_id
    )
    _logger.debug(
        "Project %s will stop %d variants", path_params.project_id, len(project_ids)
    )

    await asyncio.gather(
        *[computations.stop_computation(pid, req_ctx.user_id) for pid in project_ids]
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.get(f"/{VTAG}/computations/{{project_id}}", name="get_computation")
@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
@handle_rest_requests_exceptions
async def get_computation(request: web.Request) -> web.Response:
    dv2_client = DirectorV2RestClient(request.app)
    run_policy = get_project_run_policy(request.app)
    assert run_policy  # nosec

    user_id = request[RQT_USERID_KEY]
    path_params = parse_request_path_parameters_as(ComputationPathParams, request)

    project_ids: list[ProjectID] = await run_policy.get_runnable_projects_ids(
        request, path_params.project_id
    )

    _logger.debug(
        "Project %s will get %d variants", path_params.project_id, len(project_ids)
    )

    list_computation_tasks = await asyncio.gather(
        *[
            dv2_client.get_computation(project_id=pid, user_id=user_id)
            for pid in project_ids
        ]
    )

    assert len(list_computation_tasks) == len(project_ids)  # nosec

    return envelope_json_response(
        [
            ComputationGet.model_construct(**m.model_dump(exclude_unset=True))
            for m in list_computation_tasks
        ],
    )
