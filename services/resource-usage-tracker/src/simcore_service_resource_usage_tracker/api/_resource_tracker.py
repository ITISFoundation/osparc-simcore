import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, status
from fastapi_pagination.api import create_page
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    WalletTotalCredits,
)
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingUnitGet,
    ServicePricingPlanGet,
)
from models_library.api_schemas_resource_usage_tracker.service_runs import ServiceRunGet
from models_library.resource_tracker import CreditTransactionId

from ..models.pagination import LimitOffsetPage, LimitOffsetParamsWithDefault
from ..models.resource_tracker_service_runs import ServiceRunPage
from ..services import (
    resource_tracker_credit_transactions,
    resource_tracker_pricing_plans,
    resource_tracker_service_runs,
)

logger = logging.getLogger(__name__)


router = APIRouter()


########
# USAGE
########


@router.get(
    "/services/-/usages",
    response_model=LimitOffsetPage[ServiceRunGet],
    operation_id="list_usage_services",
    description="Returns a list of tracked containers for a given user and product",
    tags=["usages"],
)
async def list_usage_services(
    page_params: Annotated[LimitOffsetParamsWithDefault, Depends()],
    usage_services_page: Annotated[
        ServiceRunPage,
        Depends(resource_tracker_service_runs.list_service_runs),
    ],
):
    return create_page(
        usage_services_page.items,
        total=usage_services_page.total,
        params=page_params,
    )


######################
# CREDIT TRANSACTIONS
######################


@router.post(
    "/credit-transactions/credits:sum",
    response_model=WalletTotalCredits,
    summary="Sum total available credits in the wallet",
    tags=["credit-transactions"],
)
async def get_credit_transactions_sum(
    wallet_total_credits: Annotated[
        WalletTotalCredits,
        Depends(
            resource_tracker_credit_transactions.sum_credit_transactions_by_product_and_wallet
        ),
    ],
):
    return wallet_total_credits


@router.post(
    "/credit-transactions",
    response_model=dict[Literal["credit_transaction_id"], CreditTransactionId],
    summary="Top up credits for specific wallet",
    status_code=status.HTTP_201_CREATED,
    tags=["credit-transactions"],
)
async def create_credit_transaction(
    transaction_id: Annotated[
        CreditTransactionId,
        Depends(resource_tracker_credit_transactions.create_credit_transaction),
    ],
):
    return {"credit_transaction_id": transaction_id}


################
# PRICING PLANS
################


@router.get(
    "/services/{service_key:path}/{service_version}/pricing-plan",
    response_model=ServicePricingPlanGet,
    operation_id="get_service_default_pricing_plan",
    description="Returns a default pricing plan with pricing details for a specified service",
    tags=["pricing-plans"],
)
async def get_service_default_pricing_plan(
    service_pricing_plans: Annotated[
        ServicePricingPlanGet,
        Depends(resource_tracker_pricing_plans.get_service_default_pricing_plan),
    ],
):
    return service_pricing_plans


@router.get(
    "/pricing-plans/{pricing_plan_id}/pricing-units/{pricing_unit_id}",
    response_model=PricingUnitGet,
    operation_id="list_service_pricing_plans",
    description="Returns a list of service pricing plans with pricing details for a specified service",
    tags=["pricing-plans"],
)
async def get_pricing_plan_unit(
    pricing_unit: Annotated[
        PricingUnitGet,
        Depends(resource_tracker_pricing_plans.get_pricing_unit),
    ]
):
    return pricing_unit
