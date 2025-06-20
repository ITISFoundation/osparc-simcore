import functools

from aiohttp import web
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    RutPricingPlanGet,
)
from models_library.api_schemas_webserver.resource_usage import (
    ConnectServiceToPricingPlanBodyParams,
    CreatePricingPlanBodyParams,
    CreatePricingUnitBodyParams,
    PricingPlanAdminGet,
    PricingPlanToServiceAdminGet,
    PricingUnitAdminGet,
    UpdatePricingPlanBodyParams,
    UpdatePricingUnitBodyParams,
)
from models_library.resource_tracker import (
    PricingPlanCreate,
    PricingPlanId,
    PricingPlanUpdate,
    PricingUnitId,
    PricingUnitWithCostCreate,
    PricingUnitWithCostUpdate,
)
from models_library.rest_pagination import Page, PageQueryParameters
from models_library.rest_pagination_utils import paginate_data
from pydantic import BaseModel, ConfigDict
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rabbitmq._errors import RPCServerError
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    PricingUnitDuplicationError,
)
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..models import AuthenticatedRequestContext
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _pricing_plans_admin_service as pricing_plans_admin_service
from ._pricing_plans_models import PricingPlanGetPathParams

#
# API components/schemas
#


def _handle_pricing_plan_admin_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except (ValueError, PricingUnitDuplicationError) as exc:
            raise web.HTTPBadRequest(text=f"{exc}") from exc

        except RPCServerError as exc:
            # NOTE: This will be improved; we will add a mapping between
            # RPC errors and user-friendly frontend errors to pass to the frontend.
            raise RPCServerError from exc

    return wrapper


#
# API handlers
#

routes = web.RouteTableDef()


## Admin Pricing Plan endpoints


@routes.get(
    f"/{VTAG}/admin/pricing-plans",
    name="list_pricing_plans_for_admin_user",
)
@login_required
@permission_required("resource-usage.write")
@_handle_pricing_plan_admin_exceptions
async def list_pricing_plans_for_admin_user(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    query_params: PageQueryParameters = parse_request_query_parameters_as(
        PageQueryParameters, request
    )

    pricing_plan_page = (
        await pricing_plans_admin_service.list_pricing_plans_without_pricing_units(
            app=request.app,
            product_name=req_ctx.product_name,
            exclude_inactive=False,
            offset=query_params.offset,
            limit=query_params.limit,
        )
    )
    webserver_pricing_plans = [
        PricingPlanAdminGet(
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

    page = Page[PricingPlanAdminGet].model_validate(
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


def pricing_plan_get_to_admin(
    pricing_plan_get: RutPricingPlanGet,
) -> PricingPlanAdminGet:
    """
    Convert a PricingPlanGet object into a PricingPlanAdminGet object.
    """
    if pricing_plan_get.pricing_units is None:
        msg = "Pricing plan units should not be None"
        raise ValueError(msg)

    return PricingPlanAdminGet(
        pricing_plan_id=pricing_plan_get.pricing_plan_id,
        display_name=pricing_plan_get.display_name,
        description=pricing_plan_get.description,
        classification=pricing_plan_get.classification,
        created_at=pricing_plan_get.created_at,
        pricing_plan_key=pricing_plan_get.pricing_plan_key,
        pricing_units=[
            PricingUnitAdminGet(
                pricing_unit_id=pu.pricing_unit_id,
                unit_name=pu.unit_name,
                unit_extra_info=pu.unit_extra_info,
                specific_info=pu.specific_info,
                current_cost_per_unit=pu.current_cost_per_unit,
                default=pu.default,
            )
            for pu in pricing_plan_get.pricing_units
        ],
        is_active=pricing_plan_get.is_active,
    )


@routes.get(
    f"/{VTAG}/admin/pricing-plans/{{pricing_plan_id}}",
    name="get_pricing_plan_for_admin_user",
)
@login_required
@permission_required("resource-usage.write")
@_handle_pricing_plan_admin_exceptions
async def get_pricing_plan_for_admin_user(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(PricingPlanGetPathParams, request)

    pricing_plan_get = await pricing_plans_admin_service.get_pricing_plan(
        app=request.app,
        product_name=req_ctx.product_name,
        pricing_plan_id=path_params.pricing_plan_id,
    )
    webserver_admin_pricing_plan_get = pricing_plan_get_to_admin(pricing_plan_get)

    return envelope_json_response(webserver_admin_pricing_plan_get, web.HTTPOk)


@routes.post(
    f"/{VTAG}/admin/pricing-plans",
    name="create_pricing_plan",
)
@login_required
@permission_required("resource-usage.write")
@_handle_pricing_plan_admin_exceptions
async def create_pricing_plan(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    body_params = await parse_request_body_as(CreatePricingPlanBodyParams, request)

    _data = PricingPlanCreate(
        product_name=req_ctx.product_name,
        display_name=body_params.display_name,
        description=body_params.description,
        classification=body_params.classification,
        pricing_plan_key=body_params.pricing_plan_key,
    )
    pricing_plan_get = await pricing_plans_admin_service.create_pricing_plan(
        app=request.app,
        data=_data,
    )
    webserver_admin_pricing_plan_get = pricing_plan_get_to_admin(pricing_plan_get)

    return envelope_json_response(webserver_admin_pricing_plan_get, web.HTTPOk)


@routes.put(
    f"/{VTAG}/admin/pricing-plans/{{pricing_plan_id}}",
    name="update_pricing_plan",
)
@login_required
@permission_required("resource-usage.write")
@_handle_pricing_plan_admin_exceptions
async def update_pricing_plan(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(PricingPlanGetPathParams, request)
    body_params = await parse_request_body_as(UpdatePricingPlanBodyParams, request)

    _data = PricingPlanUpdate(
        pricing_plan_id=path_params.pricing_plan_id,
        display_name=body_params.display_name,
        description=body_params.description,
        is_active=body_params.is_active,
    )
    pricing_plan_get = await pricing_plans_admin_service.update_pricing_plan(
        app=request.app,
        product_name=req_ctx.product_name,
        data=_data,
    )
    webserver_admin_pricing_plan_get = pricing_plan_get_to_admin(pricing_plan_get)

    return envelope_json_response(webserver_admin_pricing_plan_get, web.HTTPOk)


## Admin Pricing Unit endpoints


class PricingUnitGetPathParams(BaseModel):
    pricing_plan_id: PricingPlanId
    pricing_unit_id: PricingUnitId
    model_config = ConfigDict(extra="forbid")


@routes.get(
    f"/{VTAG}/admin/pricing-plans/{{pricing_plan_id}}/pricing-units/{{pricing_unit_id}}",
    name="get_pricing_unit",
)
@login_required
@permission_required("resource-usage.write")
@_handle_pricing_plan_admin_exceptions
async def get_pricing_unit(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(PricingUnitGetPathParams, request)

    pricing_unit_get = await pricing_plans_admin_service.get_pricing_unit(
        app=request.app,
        product_name=req_ctx.product_name,
        pricing_plan_id=path_params.pricing_plan_id,
        pricing_unit_id=path_params.pricing_unit_id,
    )

    webserver_pricing_unit_get = PricingUnitAdminGet(
        pricing_unit_id=pricing_unit_get.pricing_unit_id,
        unit_name=pricing_unit_get.unit_name,
        unit_extra_info=pricing_unit_get.unit_extra_info,
        specific_info=pricing_unit_get.specific_info,
        current_cost_per_unit=pricing_unit_get.current_cost_per_unit,
        default=pricing_unit_get.default,
    )

    return envelope_json_response(webserver_pricing_unit_get, web.HTTPOk)


@routes.post(
    f"/{VTAG}/admin/pricing-plans/{{pricing_plan_id}}/pricing-units",
    name="create_pricing_unit",
)
@login_required
@permission_required("resource-usage.write")
@_handle_pricing_plan_admin_exceptions
async def create_pricing_unit(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(PricingPlanGetPathParams, request)
    body_params = await parse_request_body_as(CreatePricingUnitBodyParams, request)

    _data = PricingUnitWithCostCreate(
        pricing_plan_id=path_params.pricing_plan_id,
        unit_name=body_params.unit_name,
        unit_extra_info=body_params.unit_extra_info,
        default=body_params.default,
        specific_info=body_params.specific_info,
        cost_per_unit=body_params.cost_per_unit,
        comment=body_params.comment,
    )
    pricing_unit_get = await pricing_plans_admin_service.create_pricing_unit(
        app=request.app,
        product_name=req_ctx.product_name,
        data=_data,
    )

    webserver_pricing_unit_get = PricingUnitAdminGet(
        pricing_unit_id=pricing_unit_get.pricing_unit_id,
        unit_name=pricing_unit_get.unit_name,
        unit_extra_info=pricing_unit_get.unit_extra_info,
        specific_info=pricing_unit_get.specific_info,
        current_cost_per_unit=pricing_unit_get.current_cost_per_unit,
        default=pricing_unit_get.default,
    )

    return envelope_json_response(webserver_pricing_unit_get, web.HTTPOk)


@routes.put(
    f"/{VTAG}/admin/pricing-plans/{{pricing_plan_id}}/pricing-units/{{pricing_unit_id}}",
    name="update_pricing_unit",
)
@login_required
@permission_required("resource-usage.write")
@_handle_pricing_plan_admin_exceptions
async def update_pricing_unit(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(PricingUnitGetPathParams, request)
    body_params = await parse_request_body_as(UpdatePricingUnitBodyParams, request)

    _data = PricingUnitWithCostUpdate(
        pricing_plan_id=path_params.pricing_plan_id,
        pricing_unit_id=path_params.pricing_unit_id,
        unit_name=body_params.unit_name,
        unit_extra_info=body_params.unit_extra_info,
        default=body_params.default,
        specific_info=body_params.specific_info,
        pricing_unit_cost_update=body_params.pricing_unit_cost_update,
    )
    pricing_unit_get = await pricing_plans_admin_service.update_pricing_unit(
        app=request.app,
        product_name=req_ctx.product_name,
        data=_data,
    )

    webserver_pricing_unit_get = PricingUnitAdminGet(
        pricing_unit_id=pricing_unit_get.pricing_unit_id,
        unit_name=pricing_unit_get.unit_name,
        unit_extra_info=pricing_unit_get.unit_extra_info,
        specific_info=pricing_unit_get.specific_info,
        current_cost_per_unit=pricing_unit_get.current_cost_per_unit,
        default=pricing_unit_get.default,
    )

    return envelope_json_response(webserver_pricing_unit_get, web.HTTPOk)


## Admin Pricing Plans To Service endpoints


@routes.get(
    f"/{VTAG}/admin/pricing-plans/{{pricing_plan_id}}/billable-services",
    name="list_connected_services_to_pricing_plan",
)
@login_required
@permission_required("resource-usage.write")
@_handle_pricing_plan_admin_exceptions
async def list_connected_services_to_pricing_plan(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(PricingPlanGetPathParams, request)

    connected_services_list = (
        await pricing_plans_admin_service.list_connected_services_to_pricing_plan(
            app=request.app,
            product_name=req_ctx.product_name,
            pricing_plan_id=path_params.pricing_plan_id,
        )
    )
    connected_services_get = [
        PricingPlanToServiceAdminGet(
            pricing_plan_id=connected_service.pricing_plan_id,
            service_key=connected_service.service_key,
            service_version=connected_service.service_version,
            created=connected_service.created,
        )
        for connected_service in connected_services_list
    ]

    return envelope_json_response(connected_services_get, web.HTTPOk)


@routes.post(
    f"/{VTAG}/admin/pricing-plans/{{pricing_plan_id}}/billable-services",
    name="connect_service_to_pricing_plan",
)
@login_required
@permission_required("resource-usage.write")
@_handle_pricing_plan_admin_exceptions
async def connect_service_to_pricing_plan(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(PricingPlanGetPathParams, request)
    body_params = await parse_request_body_as(
        ConnectServiceToPricingPlanBodyParams, request
    )

    connected_service = (
        await pricing_plans_admin_service.connect_service_to_pricing_plan(
            app=request.app,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
            pricing_plan_id=path_params.pricing_plan_id,
            service_key=body_params.service_key,
            service_version=body_params.service_version,
        )
    )
    connected_service_get = PricingPlanToServiceAdminGet(
        pricing_plan_id=connected_service.pricing_plan_id,
        service_key=connected_service.service_key,
        service_version=connected_service.service_version,
        created=connected_service.created,
    )

    return envelope_json_response(connected_service_get, web.HTTPOk)
