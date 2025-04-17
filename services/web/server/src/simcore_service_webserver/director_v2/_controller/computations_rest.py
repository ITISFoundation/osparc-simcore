import logging

from aiohttp import web
from models_library.api_schemas_webserver.computations import (
    ComputationRunRestGet,
    ComputationTaskRestGet,
)
from models_library.rest_base import RequestParameters
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
from ._computations_rest_schema import (
    ComputationRunListQueryParams,
    ComputationTaskListQueryParams,
    ComputationTaskPathParams,
)

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
    query_params: ComputationRunListQueryParams = parse_request_query_parameters_as(
        ComputationRunListQueryParams, request
    )

    _get = await _computations_service.list_computations_latest_iteration(
        request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        # pagination
        offset=query_params.offset,
        limit=query_params.limit,
        # ordering
        order_by=query_params.order_by,
    )

    page = Page[ComputationRunRestGet].model_validate(
        paginate_data(
            chunk=[
                ComputationRunRestGet.model_validate(task, from_attributes=True)
                for task in _get.items
            ],
            total=_get.total,
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

    _get = await _computations_service.list_computations_latest_iteration_tasks(
        request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_id=path_params.project_id,
        # pagination
        offset=query_params.offset,
        limit=query_params.limit,
        # ordering
        order_by=query_params.order_by,
    )

    page = Page[ComputationTaskRestGet].model_validate(
        paginate_data(
            chunk=[
                ComputationTaskRestGet.model_validate(task, from_attributes=True)
                for task in _get.items
            ],
            total=_get.total,
            limit=query_params.limit,
            offset=query_params.offset,
            request_url=request.url,
        )
    )
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )
