import logging

from aiohttp import web
from models_library.api_schemas_webserver.computations import (
    ComputationCollectionRunListQueryParams,
    ComputationCollectionRunPathParams,
    ComputationCollectionRunRestGet,
    ComputationCollectionRunTaskListQueryParams,
    ComputationCollectionRunTaskRestGet,
    ComputationRunIterationsLatestListQueryParams,
    ComputationRunIterationsListQueryParams,
    ComputationRunPathParams,
    ComputationRunRestGet,
    ComputationTaskListQueryParams,
    ComputationTaskPathParams,
    ComputationTaskRestGet,
)
from models_library.rest_base import RequestParameters
from models_library.rest_ordering import OrderBy
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import paginate_data
from models_library.users import UserID
from pydantic import Field
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from ..._meta import API_VTAG as VTAG
from ...constants import RQ_PRODUCT_KEY
from ...login.decorators import login_required
from ...security.decorators import permission_required
from .. import _computations_service

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


class ComputationsRequestContext(RequestParameters):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


@routes.get(
    f"/{VTAG}/computations/-/iterations/latest",
    name="list_computations_latest_iteration",
)
@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
async def list_computations_latest_iteration(request: web.Request) -> web.Response:

    req_ctx = ComputationsRequestContext.model_validate(request)
    query_params: ComputationRunIterationsLatestListQueryParams = (
        parse_request_query_parameters_as(
            ComputationRunIterationsLatestListQueryParams, request
        )
    )

    total, items = await _computations_service.list_computations_latest_iteration(
        request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        # filters
        filter_only_running=query_params.filter_only_running,
        # pagination
        offset=query_params.offset,
        limit=query_params.limit,
        # ordering
        order_by=OrderBy.model_construct(**query_params.order_by.model_dump()),
    )

    page = Page[ComputationRunRestGet].model_validate(
        paginate_data(
            chunk=[
                ComputationRunRestGet.model_validate(run, from_attributes=True)
                for run in items
            ],
            total=total,
            limit=query_params.limit,
            offset=query_params.offset,
            request_url=request.url,
        )
    )

    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


@routes.get(
    f"/{VTAG}/computations/{{project_id}}/iterations",
    name="list_computation_iterations",
)
@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
async def list_computation_iterations(request: web.Request) -> web.Response:

    req_ctx = ComputationsRequestContext.model_validate(request)
    query_params: ComputationRunIterationsListQueryParams = (
        parse_request_query_parameters_as(
            ComputationRunIterationsListQueryParams, request
        )
    )
    path_params = parse_request_path_parameters_as(ComputationRunPathParams, request)

    total, items = await _computations_service.list_computation_iterations(
        request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_id=path_params.project_id,
        # filters
        include_children=query_params.include_children,
        # pagination
        offset=query_params.offset,
        limit=query_params.limit,
        # ordering
        order_by=OrderBy.model_construct(**query_params.order_by.model_dump()),
    )
    page = Page[ComputationRunRestGet].model_validate(
        paginate_data(
            chunk=[
                ComputationRunRestGet.model_validate(run, from_attributes=True)
                for run in items
            ],
            total=total,
            limit=query_params.limit,
            offset=query_params.offset,
            request_url=request.url,
        )
    )

    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


@routes.get(
    f"/{VTAG}/computations/{{project_id}}/iterations/latest/tasks",
    name="list_computations_latest_iteration_tasks",
)
@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
async def list_computations_latest_iteration_tasks(
    request: web.Request,
) -> web.Response:

    req_ctx = ComputationsRequestContext.model_validate(request)
    query_params: ComputationTaskListQueryParams = parse_request_query_parameters_as(
        ComputationTaskListQueryParams, request
    )
    path_params = parse_request_path_parameters_as(ComputationTaskPathParams, request)

    _total, _items = (
        await _computations_service.list_computations_latest_iteration_tasks(
            request.app,
            product_name=req_ctx.product_name,
            user_id=req_ctx.user_id,
            project_id=path_params.project_id,
            # filters
            include_children=query_params.include_children,
            # pagination
            offset=query_params.offset,
            limit=query_params.limit,
            # ordering
            order_by=OrderBy.model_construct(**query_params.order_by.model_dump()),
        )
    )

    page = Page[ComputationTaskRestGet].model_validate(
        paginate_data(
            chunk=[
                ComputationTaskRestGet.model_validate(task, from_attributes=True)
                for task in _items
            ],
            total=_total,
            limit=query_params.limit,
            offset=query_params.offset,
            request_url=request.url,
        )
    )
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


####  NEW:


@routes.get(
    f"/{VTAG}/computation-collection-runs",
    name="list_computation_collection_runs",
)
@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
async def list_computation_collection_runs(request: web.Request) -> web.Response:
    # Add: Filter by root project ID

    req_ctx = ComputationsRequestContext.model_validate(request)
    query_params: ComputationCollectionRunListQueryParams = (
        parse_request_query_parameters_as(
            ComputationCollectionRunListQueryParams, request
        )
    )

    total, items = await _computations_service.list_computation_collection_runs(
        request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        # filters
        filter_by_root_project_id=query_params.filter_by_root_project_id,
        # pagination
        offset=query_params.offset,
        limit=query_params.limit,
    )

    page = Page[ComputationCollectionRunRestGet].model_validate(
        paginate_data(
            chunk=[
                ComputationCollectionRunRestGet.model_validate(
                    run, from_attributes=True
                )
                for run in items
            ],
            total=total,
            limit=query_params.limit,
            offset=query_params.offset,
            request_url=request.url,
        )
    )

    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


@routes.get(
    f"/{VTAG}/computation-collection-runs/{{collection_run_id}}/tasks",  #: Who should be the owner of computation_collection_id ?
    name="list_computation_collection_run_tasks",
)
@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
async def list_computation_collection_run_tasks(request: web.Request) -> web.Response:
    # Add: Filter by root project ID

    req_ctx = ComputationsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        ComputationCollectionRunPathParams, request
    )
    query_params: ComputationCollectionRunTaskListQueryParams = (
        parse_request_query_parameters_as(
            ComputationCollectionRunTaskListQueryParams, request
        )
    )

    total, items = await _computations_service.list_computation_collection_run_tasks(
        request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        collection_run_id=path_params.collection_run_id,
        # pagination
        offset=query_params.offset,
        limit=query_params.limit,
    )

    page = Page[ComputationCollectionRunTaskRestGet].model_validate(
        paginate_data(
            chunk=[
                ComputationCollectionRunTaskRestGet.model_validate(
                    run, from_attributes=True
                )
                for run in items
            ],
            total=total,
            limit=query_params.limit,
            offset=query_params.offset,
            request_url=request.url,
        )
    )

    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )
