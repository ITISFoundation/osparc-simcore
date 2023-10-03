""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from _common import assert_handler_signature_against_model
from fastapi import APIRouter, Query
from models_library.api_schemas_webserver.resource_usage import (
    PricingUnitGet,
    ServiceRunGet,
)
from models_library.generics import Envelope
from models_library.resource_tracker import PricingPlanId, PricingUnitId
from models_library.rest_pagination import DEFAULT_NUMBER_OF_ITEMS_PER_PAGE
from models_library.wallets import WalletID
from pydantic import NonNegativeInt
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.resource_usage._pricing_plans_handlers import (
    _GetPricingPlanUnitPathParams,
)
from simcore_service_webserver.resource_usage._service_runs_handlers import (
    _ListServicesResourceUsagesPathParams,
)

router = APIRouter(prefix=f"/{API_VTAG}")


#
# API entrypoints
#


@router.get(
    "/services/-/resource-usages",
    response_model=Envelope[list[ServiceRunGet]],
    summary="Retrieve finished and currently running user services (user and product are taken from context, optionally wallet_id parameter might be provided).",
    tags=["usage"],
)
async def list_resource_usage_services(
    wallet_id: WalletID = Query(None),
    limit: int = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    offset: NonNegativeInt = 0,
):
    ...


assert_handler_signature_against_model(
    list_resource_usage_services, _ListServicesResourceUsagesPathParams
)


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
