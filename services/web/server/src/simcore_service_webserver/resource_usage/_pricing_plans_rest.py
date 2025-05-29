import functools

from aiohttp import web
from models_library.api_schemas_webserver.resource_usage import (
    PricingPlanGet,
    PricingUnitGet,
)
from models_library.resource_tracker import PricingPlanId, PricingUnitId
from models_library.rest_base import StrictRequestParameters
from models_library.rest_pagination import Page, PageQueryParameters
from models_library.rest_pagination_utils import paginate_data
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..models import RequestContext
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from ..wallets.errors import WalletAccessForbiddenError
from . import _pricing_plans_admin_service as pricing_plans_admin_service
from . import _pricing_plans_service as pricing_plans_service
from ._pricing_plans_models import PricingPlanGetPathParams

#
# API components/schemas
#


def _handle_resource_usage_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except WalletAccessForbiddenError as exc:
            raise web.HTTPForbidden(text=f"{exc}") from exc

    return wrapper


routes = web.RouteTableDef()


class PricingPlanUnitGetPathParams(StrictRequestParameters):
    pricing_plan_id: PricingPlanId
    pricing_unit_id: PricingUnitId


@routes.get(
    f"/{VTAG}/pricing-plans/{{pricing_plan_id}}/pricing-units/{{pricing_unit_id}}",
    name="get_pricing_plan_unit",
)
@login_required
@permission_required("resource-usage.read")
@_handle_resource_usage_exceptions
async def get_pricing_plan_unit(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        PricingPlanUnitGetPathParams, request
    )

    pricing_unit_get = await pricing_plans_service.get_pricing_plan_unit(
        app=request.app,
        product_name=req_ctx.product_name,
        pricing_plan_id=path_params.pricing_plan_id,
        pricing_unit_id=path_params.pricing_unit_id,
    )

    webserver_pricing_unit_get = PricingUnitGet(
        pricing_unit_id=pricing_unit_get.pricing_unit_id,
        unit_name=pricing_unit_get.unit_name,
        unit_extra_info=pricing_unit_get.unit_extra_info,
        current_cost_per_unit=pricing_unit_get.current_cost_per_unit,
        default=pricing_unit_get.default,
    )

    return envelope_json_response(webserver_pricing_unit_get, web.HTTPOk)


@routes.get(
    f"/{VTAG}/pricing-plans",
    name="list_pricing_plans",
)
@login_required
@permission_required("resource-usage.read")
@_handle_resource_usage_exceptions
async def list_pricing_plans(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    query_params: PageQueryParameters = parse_request_query_parameters_as(
        PageQueryParameters, request
    )

    pricing_plan_page = (
        await pricing_plans_admin_service.list_pricing_plans_without_pricing_units(
            app=request.app,
            product_name=req_ctx.product_name,
            exclude_inactive=True,
            offset=query_params.offset,
            limit=query_params.limit,
        )
    )
    webserver_pricing_plans = [
        PricingPlanGet(
            pricing_plan_id=pricing_plan.pricing_plan_id,
            display_name=pricing_plan.display_name,
            description=pricing_plan.description,
            classification=pricing_plan.classification,
            created_at=pricing_plan.created_at,
            pricing_plan_key=pricing_plan.pricing_plan_key,
            pricing_units=None,
            is_active=pricing_plan.is_active,
        )
        for pricing_plan in pricing_plan_page.items
    ]

    page = Page[PricingPlanGet].model_validate(
        paginate_data(
            chunk=webserver_pricing_plans,
            request_url=request.url,
            total=pricing_plan_page.total,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


@routes.get(
    f"/{VTAG}/pricing-plans/{{pricing_plan_id}}",
    name="get_pricing_plan",
)
@login_required
@permission_required("resource-usage.read")
@_handle_resource_usage_exceptions
async def get_pricing_plan(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(PricingPlanGetPathParams, request)

    pricing_plan_get = await pricing_plans_admin_service.get_pricing_plan(
        app=request.app,
        product_name=req_ctx.product_name,
        pricing_plan_id=path_params.pricing_plan_id,
    )
    if pricing_plan_get.pricing_units is None:
        msg = "Pricing plan units should not be None"
        raise ValueError(msg)

    webserver_admin_pricing_plan_get = PricingPlanGet(
        pricing_plan_id=pricing_plan_get.pricing_plan_id,
        display_name=pricing_plan_get.display_name,
        description=pricing_plan_get.description,
        classification=pricing_plan_get.classification,
        created_at=pricing_plan_get.created_at,
        pricing_plan_key=pricing_plan_get.pricing_plan_key,
        pricing_units=[
            PricingUnitGet(
                pricing_unit_id=pricing_unit.pricing_unit_id,
                unit_name=pricing_unit.unit_name,
                unit_extra_info=pricing_unit.unit_extra_info,
                current_cost_per_unit=pricing_unit.current_cost_per_unit,
                default=pricing_unit.default,
            )
            for pricing_unit in pricing_plan_get.pricing_units
        ],
        is_active=pricing_plan_get.is_active,
    )

    return envelope_json_response(webserver_admin_pricing_plan_get, web.HTTPOk)
