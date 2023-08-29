from datetime import datetime

from models_library.utils.pydantic_tools_extension import FieldNotRequired
from pydantic import Field, HttpUrl, PositiveFloat

from ..basic_types import IDStr
from ..users import GroupID
from ..wallets import (
    PaymentTransaction,
    PaymentTransactionState,
    WalletID,
    WalletStatus,
)
from ._base import OutputSchema


class WalletGet(OutputSchema):
    wallet_id: WalletID
    name: str
    description: str | None
    owner: GroupID
    thumbnail: str | None
    status: WalletStatus
    created: datetime
    modified: datetime


class WalletGetWithAvailableCredits(WalletGet):
    available_credits: float


class WalletGetPermissions(WalletGet):
    read: bool
    write: bool
    delete: bool


class CreateWalletBodyParams(OutputSchema):
    name: str
    description: str | None = None
    thumbnail: str | None = None


class PutWalletBodyParams(OutputSchema):
    name: str
    description: str | None
    thumbnail: str | None
    status: WalletStatus


class PaymentGet(OutputSchema):
    idr: IDStr  # resource identifier

    wallet_id: WalletID = Field(
        ..., description="Parent wallet, i.e. wallet that will credit this payment"
    )
    prize: PositiveFloat = Field()
    credit: PositiveFloat = Field(..., description="")
    comment: str = FieldNotRequired()

    submission_link: HttpUrl  # redirection

    # state NOTE: this might change
    state: PaymentTransactionState
    created: datetime
    completed: datetime = FieldNotRequired()

    @classmethod
    def from_transaction(
        cls, model: PaymentTransaction, *, payment_gateway_base_url: str
    ) -> "PaymentGet":
        transaction = model.dict(exclude_none=True, exclude_unset=True)
        transaction_id = model.idr
        return cls.parse_obj(
            {
                **transaction,
                "submission_link": f"{payment_gateway_base_url}/pay?{transaction_id}",
            }
        )
