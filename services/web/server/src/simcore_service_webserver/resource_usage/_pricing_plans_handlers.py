import functools

from aiohttp import web
from models_library.api_schemas_webserver.resource_usage import PricingUnitGet
from models_library.resource_tracker import PricingPlanId, PricingUnitId
from models_library.rest_base import StrictRequestParameters
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as
from servicelib.aiohttp.typing_extension import Handler

from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..models import RequestContext
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from ..wallets.errors import WalletAccessForbiddenError
from . import _pricing_plans_api as api

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

    pricing_unit_get = await api.get_pricing_plan_unit(
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
