from datetime import datetime
from decimal import Decimal

from models_library.products import ProductName
from models_library.resource_tracker import (
    CreditClassification,
    CreditTransactionId,
    CreditTransactionStatus,
    PricingPlanId,
    PricingUnitCostId,
    PricingUnitId,
    ServiceRunId,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, ConfigDict


class CreditTransactionCreate(BaseModel):
    product_name: ProductName
    wallet_id: WalletID
    wallet_name: str
    pricing_plan_id: PricingPlanId | None
    pricing_unit_id: PricingUnitId | None
    pricing_unit_cost_id: PricingUnitCostId | None
    user_id: UserID
    user_email: str
    osparc_credits: Decimal
    transaction_status: CreditTransactionStatus
    transaction_classification: CreditClassification
    service_run_id: ServiceRunId | None
    payment_transaction_id: str | None
    created_at: datetime
    last_heartbeat_at: datetime


class CreditTransactionCreditsUpdate(BaseModel):
    service_run_id: ServiceRunId
    osparc_credits: Decimal
    last_heartbeat_at: datetime


class CreditTransactionCreditsAndStatusUpdate(BaseModel):
    service_run_id: ServiceRunId
    osparc_credits: Decimal
    transaction_status: CreditTransactionStatus


class CreditTransactionDB(BaseModel):
    transaction_id: CreditTransactionId
    product_name: ProductName
    wallet_id: WalletID
    wallet_name: str
    pricing_plan_id: PricingPlanId | None
    pricing_unit_id: PricingUnitId | None
    pricing_unit_cost_id: PricingUnitCostId | None
    user_id: UserID
    user_email: str
    osparc_credits: Decimal
    transaction_status: CreditTransactionStatus
    transaction_classification: CreditClassification
    service_run_id: ServiceRunId | None
    payment_transaction_id: str | None
    created: datetime
    last_heartbeat_at: datetime
    modified: datetime
    model_config = ConfigDict(from_attributes=True)
