from datetime import datetime
from decimal import Decimal

from models_library.products import ProductName
from models_library.resource_tracker import CreditTransactionId
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, validator

from ..wallets import WalletID


class WalletTotalCredits(BaseModel):
    wallet_id: WalletID
    available_osparc_credits: Decimal

    @validator("available_osparc_credits", always=True)
    @classmethod
    def ensure_rounded(cls, v):
        return round(v, 2)


class CreditTransactionCreateBody(BaseModel):
    product_name: ProductName
    wallet_id: WalletID
    wallet_name: str
    user_id: UserID
    user_email: str
    osparc_credits: Decimal
    payment_transaction_id: str
    created_at: datetime


class CreditTransactionCreated(BaseModel):
    """Response Create Credit Transaction V1 Credit Transactions Post"""

    credit_transaction_id: CreditTransactionId
