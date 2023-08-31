from datetime import datetime

from models_library.products import ProductName
from models_library.resource_tracker import (
    PricingDetailId,
    PricingPlanId,
    ServiceRunId,
    TransactionBillingStatus,
    TransactionClassification,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel


class CreditTransactionCreate(BaseModel):
    product_name: ProductName
    wallet_id: WalletID
    wallet_name: str
    pricing_plan_id: PricingPlanId | None
    pricing_detail_id: PricingDetailId | None
    user_id: UserID
    user_email: str
    credits: float
    transaction_status: TransactionBillingStatus
    transaction_classification: TransactionClassification
    service_run_id: ServiceRunId | None
    payment_transaction_id: str | None
    created_at: datetime
    last_heartbeat_at: datetime


class CreditTransactionCreditsUpdate(BaseModel):
    service_run_id: ServiceRunId
    credits: float
    last_heartbeat_at: datetime


class CreditTransactionCreditsAndStatusUpdate(BaseModel):
    service_run_id: ServiceRunId
    credits: float
    transaction_status: TransactionBillingStatus
