from datetime import datetime

from pydantic import BaseModel, HttpUrl, PositiveFloat

from ..basic_types import IDStr
from ..wallets import PaymentTransactionState, WalletID


class PaymentGet(BaseModel):
    idr: IDStr
    prize: PositiveFloat
    wallet_id: WalletID
    credit: PositiveFloat
    comment: str
    state: PaymentTransactionState
    created: datetime
    completed: datetime | None

    submission_link: HttpUrl  # redirection
