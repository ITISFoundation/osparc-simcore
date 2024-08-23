import functools

from aiohttp import web
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
from models_library.users import UserID
from pydantic import BaseModel, Extra, Field
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    CustomResourceUsageTrackerError,
)
from servicelib.request_keys import RQT_USERID_KEY

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _pricing_plans_admin_api as admin_api

#
# API components/schemas
#


def _handle_pricing_plan_admin_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except CustomResourceUsageTrackerError as exc:
            raise CustomResourceUsageTrackerError from exc

    return wrapper


class _RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


#
# API handlers
#

routes = web.RouteTableDef()


## Admin Pricing Plan endpoints


class _GetPricingPlanPathParams(BaseModel):
    pricing_plan_id: PricingPlanId

    class Config:
        extra = Extra.forbid


@routes.get(
    f"/{VTAG}/admin/pricing-plans",
    name="list_pricing_plans",
)
@login_required
@permission_required("resource-usage.write")
@_handle_pricing_plan_admin_exceptions
async def list_pricing_plans(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)

    pricing_plans_list = await admin_api.list_pricing_plans(
        app=request.app,
        product_name=req_ctx.product_name,
    )
    webserver_pricing_unit_get = [
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
        for pricing_plan in pricing_plans_list
    ]

    return envelope_json_response(webserver_pricing_unit_get, web.HTTPOk)


@routes.get(
    f"/{VTAG}/admin/pricing-plans/{{pricing_plan_id}}",
    name="get_pricing_plan",
)
@login_required
@permission_required("resource-usage.write")
@_handle_pricing_plan_admin_exceptions
async def get_pricing_plan(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_GetPricingPlanPathParams, request)

    pricing_plan_get = await admin_api.get_pricing_plan(
        app=request.app,
        product_name=req_ctx.product_name,
        pricing_plan_id=path_params.pricing_plan_id,
    )
    if pricing_plan_get.pricing_units is None:
        raise ValueError("Pricing plan units should not be None")

    webserver_admin_pricing_plan_get = PricingPlanAdminGet(
        pricing_plan_id=pricing_plan_get.pricing_plan_id,
        display_name=pricing_plan_get.display_name,
        description=pricing_plan_get.description,
        classification=pricing_plan_get.classification,
        created_at=pricing_plan_get.created_at,
        pricing_plan_key=pricing_plan_get.pricing_plan_key,
        pricing_units=[
            PricingUnitAdminGet(
                pricing_unit_id=pricing_unit.pricing_unit_id,
                unit_name=pricing_unit.unit_name,
                unit_extra_info=pricing_unit.unit_extra_info,  # type: ignore[arg-type]
                specific_info=pricing_unit.specific_info,
                current_cost_per_unit=pricing_unit.current_cost_per_unit,
                default=pricing_unit.default,
            )
            for pricing_unit in pricing_plan_get.pricing_units
        ],
        is_active=pricing_plan_get.is_active,
    )

    return envelope_json_response(webserver_admin_pricing_plan_get, web.HTTPOk)


@routes.post(
    f"/{VTAG}/admin/pricing-plans",
    name="create_pricing_plan",
)
@login_required
@permission_required("resource-usage.write")
@_handle_pricing_plan_admin_exceptions
async def create_pricing_plan(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    body_params = await parse_request_body_as(CreatePricingPlanBodyParams, request)

    _data = PricingPlanCreate(
        product_name=req_ctx.product_name,
        display_name=body_params.display_name,
        description=body_params.description,
        classification=body_params.classification,
        pricing_plan_key=body_params.pricing_plan_key,
    )
    pricing_plan_get = await admin_api.create_pricing_plan(
        app=request.app,
        data=_data,
    )
    if pricing_plan_get.pricing_units is None:
        raise ValueError

    webserver_admin_pricing_plan_get = PricingPlanAdminGet(
        pricing_plan_id=pricing_plan_get.pricing_plan_id,
        display_name=pricing_plan_get.display_name,
        description=pricing_plan_get.description,
        classification=pricing_plan_get.classification,
        created_at=pricing_plan_get.created_at,
        pricing_plan_key=pricing_plan_get.pricing_plan_key,
        pricing_units=[
            PricingUnitAdminGet(
                pricing_unit_id=pricing_unit.pricing_unit_id,
                unit_name=pricing_unit.unit_name,
                unit_extra_info=pricing_unit.unit_extra_info,  # type: ignore[arg-type]
                specific_info=pricing_unit.specific_info,
                current_cost_per_unit=pricing_unit.current_cost_per_unit,
                default=pricing_unit.default,
            )
            for pricing_unit in pricing_plan_get.pricing_units
        ],
        is_active=pricing_plan_get.is_active,
    )

    return envelope_json_response(webserver_admin_pricing_plan_get, web.HTTPOk)


@routes.put(
    f"/{VTAG}/admin/pricing-plans/{{pricing_plan_id}}",
    name="update_pricing_plan",
)
@login_required
@permission_required("resource-usage.write")
@_handle_pricing_plan_admin_exceptions
async def update_pricing_plan(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_GetPricingPlanPathParams, request)
    body_params = await parse_request_body_as(UpdatePricingPlanBodyParams, request)

    _data = PricingPlanUpdate(
        pricing_plan_id=path_params.pricing_plan_id,
        display_name=body_params.display_name,
        description=body_params.description,
        is_active=body_params.is_active,
    )
    pricing_plan_get = await admin_api.update_pricing_plan(
        app=request.app,
        product_name=req_ctx.product_name,
        data=_data,
    )
    if pricing_plan_get.pricing_units is None:
        raise ValueError

    webserver_admin_pricing_plan_get = PricingPlanAdminGet(
        pricing_plan_id=pricing_plan_get.pricing_plan_id,
        display_name=pricing_plan_get.display_name,
        description=pricing_plan_get.description,
        classification=pricing_plan_get.classification,
        created_at=pricing_plan_get.created_at,
        pricing_plan_key=pricing_plan_get.pricing_plan_key,
        pricing_units=[
            PricingUnitAdminGet(
                pricing_unit_id=pricing_unit.pricing_unit_id,
                unit_name=pricing_unit.unit_name,
                unit_extra_info=pricing_unit.unit_extra_info,  # type: ignore[arg-type]
                specific_info=pricing_unit.specific_info,
                current_cost_per_unit=pricing_unit.current_cost_per_unit,
                default=pricing_unit.default,
            )
            for pricing_unit in pricing_plan_get.pricing_units
        ],
        is_active=pricing_plan_get.is_active,
    )

    return envelope_json_response(webserver_admin_pricing_plan_get, web.HTTPOk)


## Admin Pricing Unit endpoints


class _GetPricingUnitPathParams(BaseModel):
    pricing_plan_id: PricingPlanId
    pricing_unit_id: PricingUnitId

    class Config:
        extra = Extra.forbid


@routes.get(
    f"/{VTAG}/admin/pricing-plans/{{pricing_plan_id}}/pricing-units/{{pricing_unit_id}}",
    name="get_pricing_unit",
)
@login_required
@permission_required("resource-usage.write")
@_handle_pricing_plan_admin_exceptions
async def get_pricing_unit(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_GetPricingUnitPathParams, request)

    pricing_unit_get = await admin_api.get_pricing_unit(
        app=request.app,
        product_name=req_ctx.product_name,
        pricing_plan_id=path_params.pricing_plan_id,
        pricing_unit_id=path_params.pricing_unit_id,
    )

    webserver_pricing_unit_get = PricingUnitAdminGet(
        pricing_unit_id=pricing_unit_get.pricing_unit_id,
        unit_name=pricing_unit_get.unit_name,
        unit_extra_info=pricing_unit_get.unit_extra_info,  # type: ignore[arg-type]
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
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_GetPricingPlanPathParams, request)
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
    pricing_unit_get = await admin_api.create_pricing_unit(
        app=request.app,
        product_name=req_ctx.product_name,
        data=_data,
    )

    webserver_pricing_unit_get = PricingUnitAdminGet(
        pricing_unit_id=pricing_unit_get.pricing_unit_id,
        unit_name=pricing_unit_get.unit_name,
        unit_extra_info=pricing_unit_get.unit_extra_info,  # type: ignore[arg-type]
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
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_GetPricingUnitPathParams, request)
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
    pricing_unit_get = await admin_api.update_pricing_unit(
        app=request.app,
        product_name=req_ctx.product_name,
        data=_data,
    )

    webserver_pricing_unit_get = PricingUnitAdminGet(
        pricing_unit_id=pricing_unit_get.pricing_unit_id,
        unit_name=pricing_unit_get.unit_name,
        unit_extra_info=pricing_unit_get.unit_extra_info,  # type: ignore[arg-type]
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
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_GetPricingPlanPathParams, request)

    connected_services_list = await admin_api.list_connected_services_to_pricing_plan(
        app=request.app,
        product_name=req_ctx.product_name,
        pricing_plan_id=path_params.pricing_plan_id,
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
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_GetPricingPlanPathParams, request)
    body_params = await parse_request_body_as(
        ConnectServiceToPricingPlanBodyParams, request
    )

    connected_service = await admin_api.connect_service_to_pricing_plan(
        app=request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        pricing_plan_id=path_params.pricing_plan_id,
        service_key=body_params.service_key,
        service_version=body_params.service_version,
    )
    connected_service_get = PricingPlanToServiceAdminGet(
        pricing_plan_id=connected_service.pricing_plan_id,
        service_key=connected_service.service_key,
        service_version=connected_service.service_version,
        created=connected_service.created,
    )

    return envelope_json_response(connected_service_get, web.HTTPOk)
