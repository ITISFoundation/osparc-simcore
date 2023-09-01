from datetime import datetime
from decimal import Decimal
from typing import TypeAlias

from pydantic import BaseModel, Field, HttpUrl

from ..basic_types import IDStr
from ..utils.pydantic_tools_extension import FieldNotRequired
from ..wallets import PaymentTransactionState, WalletID

PaymentID: TypeAlias = IDStr  # identifier associated to a payment transaction


class PaymentGet(BaseModel):
    payment_id: PaymentID
    submission_link: HttpUrl = Field(
        ..., description="Link to external site that holds the payment submission form"
    )


class PaymentItemList(BaseModel):
    payment_id: PaymentID
    price_dollars: Decimal
    wallet_id: WalletID
    credit: Decimal
    comment: str = FieldNotRequired()
    state: PaymentTransactionState
    created: datetime
    completed: datetime | None
