from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, PositiveFloat

from ..basic_types import IDStr
from ..utils.pydantic_tools_extension import FieldNotRequired
from ..wallets import PaymentTransactionState, WalletID


class PaymentGet(BaseModel):
    idr: IDStr
    prize: PositiveFloat
    wallet_id: WalletID
    credit: PositiveFloat
    comment: str = FieldNotRequired()
    state: PaymentTransactionState
    created: datetime
    completed: datetime | None

    submission_link: HttpUrl = Field(
        ..., description="Link to external site that holds the payment submission form"
    )
