import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    CreditTransactionCreated,
    WalletTotalCredits,
)
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanGet,
    PricingUnitGet,
)
from models_library.resource_tracker import CreditTransactionId

from ...services import credit_transactions, pricing_plans, pricing_units

_logger = logging.getLogger(__name__)


router = APIRouter()


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
        Depends(credit_transactions.sum_credit_transactions_by_product_and_wallet),
    ],
):
    return wallet_total_credits


@router.post(
    "/credit-transactions",
    response_model=CreditTransactionCreated,
    summary="Top up credits for specific wallet",
    status_code=status.HTTP_201_CREATED,
    tags=["credit-transactions"],
)
async def create_credit_transaction(
    transaction_id: Annotated[
        CreditTransactionId,
        Depends(credit_transactions.create_credit_transaction),
    ],
):
    return {"credit_transaction_id": transaction_id}


################
# PRICING PLANS
################


@router.get(
    "/services/{service_key:path}/{service_version}/pricing-plan",
    response_model=PricingPlanGet,
    operation_id="get_service_default_pricing_plan",
    description="Returns a default pricing plan with pricing details for a specified service",
    tags=["pricing-plans"],
)
async def get_service_default_pricing_plan(
    service_pricing_plans: Annotated[
        PricingPlanGet,
        Depends(pricing_plans.get_service_default_pricing_plan),
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
        Depends(pricing_units.get_pricing_unit),
    ]
):
    return pricing_unit
