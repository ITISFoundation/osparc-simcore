from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, HttpUrl

from ..basic_types import IDStr
from ..utils.pydantic_tools_extension import FieldNotRequired
from ..wallets import PaymentTransactionState, WalletID


class PaymentGet(BaseModel):
    idr: IDStr
    submission_link: HttpUrl = Field(
        ..., description="Link to external site that holds the payment submission form"
    )


class PaymentItemList(BaseModel):
    idr: IDStr
    price_dollars: Decimal
    wallet_id: WalletID
    credit: Decimal
    comment: str = FieldNotRequired()
    state: PaymentTransactionState
    created: datetime
    completed: datetime | None
