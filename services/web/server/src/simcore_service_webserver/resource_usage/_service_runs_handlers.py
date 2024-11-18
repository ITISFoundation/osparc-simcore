import functools
from typing import Any

from aiohttp import web
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    OsparcCreditsAggregatedUsagesPage,
    ServiceRunPage,
)
from models_library.basic_types import IDStr
from models_library.resource_tracker import (
    ServiceResourceUsagesFilters,
    ServicesAggregatedUsagesTimePeriod,
    ServicesAggregatedUsagesType,
)
from models_library.rest_base import RequestParameters
from models_library.rest_ordering import (
    OrderBy,
    OrderDirection,
    create_ordering_query_model_classes,
)
from models_library.rest_pagination import Page, PageQueryParameters
from models_library.rest_pagination_utils import paginate_data
from models_library.wallets import WalletID
from pydantic import Extra, Field, Json, parse_obj_as, validator
from servicelib.aiohttp.requests_validation import parse_request_query_parameters_as
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..models import RequestContext
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


_ResorceUsagesListOrderQueryParams: type[
    RequestParameters
] = create_ordering_query_model_classes(
    ordering_fields={
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
    },
    default=OrderBy(field=IDStr("started_at"), direction=OrderDirection.DESC),
)


class ServicesResourceUsagesReportQueryParams(
    _ResorceUsagesListOrderQueryParams  # type: ignore[misc, valid-type]
):
    wallet_id: WalletID | None = Field(default=None)
    filters: (
        Json[ServiceResourceUsagesFilters]  # pylint: disable=unsubscriptable-object
        | None
    ) = Field(
        default=None,
        description="Filters to process on the resource usages list, encoded as JSON. Currently supports the filtering of 'started_at' field with 'from' and 'until' parameters in <yyyy-mm-dd> ISO 8601 format. The date range specified is inclusive.",
        example='{"started_at": {"from": "yyyy-mm-dd", "until": "yyyy-mm-dd"}}',
    )

    @validator("order_by", always=True)
    @classmethod
    def _post_rename_order_by_field_as_db_column(cls, v):
        if v.field == "credit_cost":  # API field
            v.field = "osparc_credits"  # DB column
        return v

    class Config:
        extra = Extra.forbid


class ServicesResourceUsagesListQueryParams(
    PageQueryParameters, ServicesResourceUsagesReportQueryParams
):
    class Config:
        extra = Extra.forbid


class ServicesAggregatedUsagesListQueryParams(PageQueryParameters):
    aggregated_by: ServicesAggregatedUsagesType
    time_period: ServicesAggregatedUsagesTimePeriod
    wallet_id: WalletID

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
    req_ctx = RequestContext.parse_obj(request)
    query_params: ServicesResourceUsagesListQueryParams = (
        parse_request_query_parameters_as(
            ServicesResourceUsagesListQueryParams, request
        )
    )

    services: ServiceRunPage = await api.list_usage_services(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        wallet_id=query_params.wallet_id,
        offset=query_params.offset,
        limit=query_params.limit,
        order_by=parse_obj_as(OrderBy, query_params.order_by),
        filters=parse_obj_as(ServiceResourceUsagesFilters | None, query_params.filters),  # type: ignore[arg-type] # from pydantic v2 --> https://github.com/pydantic/pydantic/discussions/4950
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


@routes.get(
    f"/{VTAG}/services/-/aggregated-usages",
    name="list_osparc_credits_aggregated_usages",
)
@login_required
@permission_required("resource-usage.read")
@_handle_resource_usage_exceptions
async def list_osparc_credits_aggregated_usages(request: web.Request):
    req_ctx = RequestContext.parse_obj(request)
    query_params: ServicesAggregatedUsagesListQueryParams = (
        parse_request_query_parameters_as(
            ServicesAggregatedUsagesListQueryParams, request
        )
    )

    aggregated_services: OsparcCreditsAggregatedUsagesPage = (
        await api.get_osparc_credits_aggregated_usages_page(
            app=request.app,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
            wallet_id=query_params.wallet_id,
            aggregated_by=query_params.aggregated_by,
            time_period=query_params.time_period,
            offset=query_params.offset,
            limit=query_params.limit,
        )
    )

    page = Page[dict[str, Any]].parse_obj(
        paginate_data(
            chunk=aggregated_services.items,
            request_url=request.url,
            total=aggregated_services.total,
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
    req_ctx = RequestContext.parse_obj(request)
    query_params: ServicesResourceUsagesReportQueryParams = (
        parse_request_query_parameters_as(
            ServicesResourceUsagesReportQueryParams, request
        )
    )
    download_url = await api.export_usage_services(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        wallet_id=query_params.wallet_id,
        order_by=parse_obj_as(OrderBy | None, query_params.order_by),  # type: ignore[arg-type] # from pydantic v2 --> https://github.com/pydantic/pydantic/discussions/4950
        filters=parse_obj_as(ServiceResourceUsagesFilters | None, query_params.filters),  # type: ignore[arg-type] # from pydantic v2 --> https://github.com/pydantic/pydantic/discussions/4950
    )
    raise web.HTTPFound(location=f"{download_url}")
