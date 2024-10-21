from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, PlainSerializer

from ..products import ProductName
from ..resource_tracker import CreditTransactionId
from ..users import UserID
from ..wallets import WalletID


class WalletTotalCredits(BaseModel):
    wallet_id: WalletID
    available_osparc_credits: Annotated[
        Decimal,
        BeforeValidator(lambda x: round(x, 2)),
        PlainSerializer(float, return_type=float, when_used="json"),
    ]


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
