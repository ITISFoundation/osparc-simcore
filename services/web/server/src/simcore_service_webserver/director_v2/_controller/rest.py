import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
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
from ...models import AuthenticatedRequestContext
from ...products import products_web
from ...projects.projects_metadata_service import (
    get_project_custom_metadata_or_empty_dict,
)
from ...security.decorators import permission_required
from ...utils_aiohttp import envelope_json_response, get_api_base_url
from .. import _director_v2_service
from .._client import DirectorV2RestClient
from .._comp_run_collections_models import CompRunCollectionDBGet
from .._comp_run_collections_service import (
    create_comp_run_collection,
    get_comp_run_collection_or_none_by_client_generated_id,
)
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
    req_ctx = AuthenticatedRequestContext.model_validate(request)
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

    # Get Project custom metadata information
    # inject the collection_id to the options
    custom_metadata = await get_project_custom_metadata_or_empty_dict(
        request.app, project_uuid=path_params.project_id
    )
    group_id_or_none = custom_metadata.get("group_id")

    comp_run_collection: CompRunCollectionDBGet | None
    if group_id_or_none:
        comp_run_collection = await get_comp_run_collection_or_none_by_client_generated_id(
            request.app, client_generated_id=group_id_or_none  # type: ignore
        )
    if comp_run_collection is not None:
        created_at: datetime = comp_run_collection.created
        now = datetime.now(UTC)
        if now - created_at > timedelta(minutes=5):
            raise web.HTTPBadRequest(
                reason=(
                    "This client generated collection is not new, "
                    "it was created more than 5 minutes ago. "
                    "Therefore, the client is probably wrongly generating it."
                )
            )
    generated_by_system = False
    if group_id_or_none in {None, "", "00000000-0000-0000-0000-000000000000"}:
        generated_by_system = True
        client_or_system_generated_id = (
            f"system-generated-{path_params.project_id}{uuid.uuid4}"
        )
    else:
        # assert isinstance(group_id_or_none, str)  # nosec
        # assert uuid.UUID(group_id_or_none)
        client_or_system_generated_id = f"{group_id_or_none}"
    group_name = custom_metadata.get("group_name", "No Group Name")
    # job_name_or_none = custom_metadata.get("job_name")

    collection_id = await create_comp_run_collection(
        request.app,
        client_or_system_generated_id=client_or_system_generated_id,
        client_or_system_generated_display_name=group_name,  # type: ignore
        generated_by_system=generated_by_system,
    )

    options = {
        "start_pipeline": True,
        "subgraph": list(subgraph),  # sets are not natively json serializable
        "force_restart": force_restart,
        "simcore_user_agent": simcore_user_agent,
        "use_on_demand_clusters": group_properties.use_on_demand_clusters,
        "wallet_info": wallet_info,
        "collection_id": collection_id,
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
                pid,
                req_ctx.user_id,
                req_ctx.product_name,
                get_api_base_url(request),
                **options,
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
    req_ctx = AuthenticatedRequestContext.model_validate(request)
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
