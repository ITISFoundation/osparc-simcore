import functools
from typing import Any

from aiohttp import web
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    ServiceRunPage,
)
from models_library.resource_tracker import ServiceResourceUsagesFilters
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    Page,
)
from models_library.rest_pagination_utils import paginate_data
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import (
    BaseModel,
    Extra,
    Field,
    Json,
    NonNegativeInt,
    parse_obj_as,
    validator,
)
from servicelib.aiohttp.requests_validation import parse_request_query_parameters_as
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..wallets.errors import WalletAccessForbiddenError
from . import _service_runs_api as api

#
# API components/schemas
#


def _handle_resource_usage_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except WalletAccessForbiddenError as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return wrapper


class _RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[pydantic-alias]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[pydantic-alias]


ORDER_BY_DESCRIPTION = "Order by field (wallet_id|wallet_name|user_id|project_id|project_name|node_id|node_name|service_key|service_version|service_type|started_at|stopped_at|service_run_status|credit_cost|transaction_status) and direction (asc|desc). The default sorting order is ascending."


class _ListServicesResourceUsagesQueryParams(BaseModel):
    wallet_id: WalletID | None = Field(default=None)
    order_by: Json[OrderBy] = Field(  # pylint: disable=unsubscriptable-object
        default=OrderBy(field="started_at", direction=OrderDirection.DESC),
        description=ORDER_BY_DESCRIPTION,
        example='{"field": "started_at", "direction": "desc"}',
    )
    filters: Json[  # pylint: disable=unsubscriptable-object
        ServiceResourceUsagesFilters
    ] | None = Field(
        default=None,
        description="Filters to process on the resource usages list, encoded as JSON. Currently supports the filtering of 'started_at' field with 'from' and 'until' parameters in <yyyy-mm-dd> ISO 8601 format. The date range specified is inclusive.",
        example='{"started_at": {"from": "yyyy-mm-dd", "until": "yyyy-mm-dd"}}',
    )

    @validator("order_by", allow_reuse=True)
    @classmethod
    def validate_order_by_field(cls, v):
        if v.field not in {
            "wallet_id",
            "wallet_name",
            "user_id",
            "user_email",
            "project_id",
            "project_name",
            "node_id",
            "node_name",
            "root_parent_project_id",
            "root_parent_project_name",
            "service_key",
            "service_version",
            "service_type",
            "started_at",
            "stopped_at",
            "service_run_status",
            "credit_cost",
            "transaction_status",
        }:
            raise ValueError(f"We do not support ordering by provided field {v.field}")
        if v.field == "credit_cost":
            v.field = "osparc_credits"
        return v

    class Config:
        extra = Extra.forbid


class _ListServicesResourceUsagesQueryParamsWithPagination(
    _ListServicesResourceUsagesQueryParams
):
    limit: int = Field(
        default=DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        description="maximum number of items to return (pagination)",
        ge=1,
        lt=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    )
    offset: NonNegativeInt = Field(
        default=0, description="index to the first item to return (pagination)"
    )

    class Config:
        extra = Extra.forbid


#
# API handlers
#

routes = web.RouteTableDef()


@routes.get(f"/{VTAG}/services/-/resource-usages", name="list_resource_usage_services")
@login_required
@permission_required("resource-usage.read")
@_handle_resource_usage_exceptions
async def list_resource_usage_services(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(
        _ListServicesResourceUsagesQueryParamsWithPagination, request
    )

    services: ServiceRunPage = await api.list_usage_services(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        wallet_id=query_params.wallet_id,
        offset=query_params.offset,
        limit=query_params.limit,
        order_by=parse_obj_as(OrderBy, query_params.order_by),
        filters=parse_obj_as(ServiceResourceUsagesFilters | None, query_params.filters),
    )

    page = Page[dict[str, Any]].parse_obj(
        paginate_data(
            chunk=services.items,
            request_url=request.url,
            total=services.total,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


@routes.get(f"/{VTAG}/services/-/usage-report", name="export_resource_usage_services")
@login_required
@permission_required("resource-usage.read")
@_handle_resource_usage_exceptions
async def export_resource_usage_services(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(
        _ListServicesResourceUsagesQueryParams, request
    )
    download_url = await api.export_usage_services(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        wallet_id=query_params.wallet_id,
        order_by=parse_obj_as(OrderBy | None, query_params.order_by),
        filters=parse_obj_as(ServiceResourceUsagesFilters | None, query_params.filters),
    )
    raise web.HTTPFound(location=f"{download_url}")
