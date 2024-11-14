""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from _common import assert_handler_signature_against_model
from fastapi import APIRouter, Depends, Query, status
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    OsparcCreditsAggregatedByServiceGet,
)
from models_library.api_schemas_webserver.resource_usage import (
    ConnectServiceToPricingPlanBodyParams,
    CreatePricingPlanBodyParams,
    CreatePricingUnitBodyParams,
    PricingPlanAdminGet,
    PricingPlanToServiceAdminGet,
    PricingUnitAdminGet,
    PricingUnitGet,
    ServiceRunGet,
    UpdatePricingPlanBodyParams,
    UpdatePricingUnitBodyParams,
)
from models_library.generics import Envelope
from models_library.resource_tracker import (
    PricingPlanId,
    PricingUnitId,
    ServicesAggregatedUsagesTimePeriod,
    ServicesAggregatedUsagesType,
)
from models_library.rest_base import RequestParameters
from models_library.rest_pagination import PageQueryParameters
from models_library.wallets import WalletID
from pydantic import Json
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.resource_usage._pricing_plans_admin_handlers import (
    _GetPricingPlanPathParams,
    _GetPricingUnitPathParams,
)
from simcore_service_webserver.resource_usage._pricing_plans_handlers import (
    _GetPricingPlanUnitPathParams,
)
from simcore_service_webserver.resource_usage._service_runs_handlers import (
    ListResourceUsagesOrderQueryParamsOpenApi,
)


class _FiltersQueryParams(RequestParameters):
    filters: Annotated[
        Json | None,
        Query(
            description="Filters to process on the resource usages list, encoded as JSON. "
            "Currently supports the filtering of 'started_at' field with 'from' and 'until' parameters in <yyyy-mm-dd> ISO 8601 format. "
            "The date range specified is inclusive.",
            example='{"started_at": {"from": "yyyy-mm-dd", "until": "yyyy-mm-dd"}}',
        ),
    ] = None


class _OrderQueryParams(ListResourceUsagesOrderQueryParamsOpenApi):
    ...


class _ListQueryParams(  # type: ignore
    _OrderQueryParams,
    _FiltersQueryParams,
    PageQueryParameters,
):
    ...


router = APIRouter(prefix=f"/{API_VTAG}")


@router.get(
    "/services/-/resource-usages",
    response_model=Envelope[list[ServiceRunGet]],
    summary="Retrieve finished and currently running user services"
    " (user and product are taken from context, optionally wallet_id parameter might be provided).",
    tags=["usage"],
)
async def list_resource_usage_services(
    _q: Annotated[_ListQueryParams, Depends()],
    wallet_id: Annotated[WalletID | None, Query] = None,
):
    ...


@router.get(
    "/services/-/aggregated-usages",
    response_model=Envelope[list[OsparcCreditsAggregatedByServiceGet]],
    summary="Used credits based on aggregate by type, currently supported `services`"
    ". (user and product are taken from context, optionally wallet_id parameter might be provided).",
    tags=["usage"],
)
async def list_osparc_credits_aggregated_usages(
    aggregated_by: ServicesAggregatedUsagesType,
    time_period: ServicesAggregatedUsagesTimePeriod,
    wallet_id: Annotated[WalletID, Query],
    _q: Annotated[PageQueryParameters, Depends()],
):
    ...


@router.get(
    "/services/-/usage-report",
    status_code=status.HTTP_302_FOUND,
    responses={
        status.HTTP_302_FOUND: {
            "description": "redirection to download link",
        }
    },
    tags=["usage"],
    summary="Redirects to download CSV link. CSV obtains finished and currently running "
    "user services (user and product are taken from context, optionally wallet_id parameter might be provided).",
)
async def export_resource_usage_services(
    _oq: Annotated[_OrderQueryParams, Depends()],
    _fq: Annotated[_FiltersQueryParams, Depends()],
    wallet_id: Annotated[WalletID | None, Query] = None,
):
    ...


@router.get(
    "/pricing-plans/{pricing_plan_id}/pricing-units/{pricing_unit_id}",
    response_model=Envelope[PricingUnitGet],
    summary="Retrieve detail information about pricing unit",
    tags=["pricing-plans"],
)
async def get_pricing_plan_unit(
    pricing_plan_id: PricingPlanId, pricing_unit_id: PricingUnitId
):
    ...


assert_handler_signature_against_model(
    get_pricing_plan_unit, _GetPricingPlanUnitPathParams
)


## Pricing plans for Admin panel


@router.get(
    "/admin/pricing-plans",
    response_model=Envelope[list[PricingPlanAdminGet]],
    summary="List pricing plans",
    tags=["admin"],
    description="To keep the listing lightweight, the pricingUnits field is None.",
)
async def list_pricing_plans():
    ...


@router.get(
    "/admin/pricing-plans/{pricing_plan_id}",
    response_model=Envelope[PricingPlanAdminGet],
    summary="Retrieve detail information about pricing plan",
    tags=["admin"],
)
async def get_pricing_plan(
    pricing_plan_id: PricingPlanId,
):
    ...


assert_handler_signature_against_model(get_pricing_plan, _GetPricingPlanPathParams)


@router.post(
    "/admin/pricing-plans",
    response_model=Envelope[PricingPlanAdminGet],
    summary="Create pricing plan",
    tags=["admin"],
)
async def create_pricing_plan(
    _b: CreatePricingPlanBodyParams,
):
    ...


@router.put(
    "/admin/pricing-plans/{pricing_plan_id}",
    response_model=Envelope[PricingPlanAdminGet],
    summary="Update detail information about pricing plan",
    tags=["admin"],
)
async def update_pricing_plan(
    pricing_plan_id: PricingPlanId,
    _b: UpdatePricingPlanBodyParams,
):
    ...


assert_handler_signature_against_model(update_pricing_plan, _GetPricingPlanPathParams)


## Pricing units for Admin panel


@router.get(
    "/admin/pricing-plans/{pricing_plan_id}/pricing-units/{pricing_unit_id}",
    response_model=Envelope[PricingUnitAdminGet],
    summary="Retrieve detail information about pricing unit",
    tags=["admin"],
)
async def get_pricing_unit(
    pricing_plan_id: PricingPlanId,
    pricing_unit_id: PricingUnitId,
):
    ...


assert_handler_signature_against_model(get_pricing_unit, _GetPricingUnitPathParams)


@router.post(
    "/admin/pricing-plans/{pricing_plan_id}/pricing-units",
    response_model=Envelope[PricingUnitAdminGet],
    summary="Create pricing unit",
    tags=["admin"],
)
async def create_pricing_unit(
    pricing_plan_id: PricingPlanId,
    _b: CreatePricingUnitBodyParams,
):
    ...


assert_handler_signature_against_model(create_pricing_unit, _GetPricingPlanPathParams)


@router.put(
    "/admin/pricing-plans/{pricing_plan_id}/pricing-units/{pricing_unit_id}",
    response_model=Envelope[PricingUnitAdminGet],
    summary="Update detail information about pricing plan",
    tags=["admin"],
)
async def update_pricing_unit(
    pricing_plan_id: PricingPlanId,
    pricing_unit_id: PricingUnitId,
    _b: UpdatePricingUnitBodyParams,
):
    ...


assert_handler_signature_against_model(update_pricing_unit, _GetPricingUnitPathParams)


## Pricing Plans to Service Admin panel


@router.get(
    "/admin/pricing-plans/{pricing_plan_id}/billable-services",
    response_model=Envelope[list[PricingPlanToServiceAdminGet]],
    summary="List services that are connected to the provided pricing plan",
    tags=["admin"],
)
async def list_connected_services_to_pricing_plan(
    pricing_plan_id: PricingPlanId,
):
    ...


assert_handler_signature_against_model(update_pricing_unit, _GetPricingPlanPathParams)


@router.post(
    "/admin/pricing-plans/{pricing_plan_id}/billable-services",
    response_model=Envelope[PricingPlanToServiceAdminGet],
    summary="Connect service with pricing plan",
    tags=["admin"],
)
async def connect_service_to_pricing_plan(
    pricing_plan_id: PricingPlanId,
    _b: ConnectServiceToPricingPlanBodyParams,
):
    ...


assert_handler_signature_against_model(update_pricing_unit, _GetPricingPlanPathParams)
