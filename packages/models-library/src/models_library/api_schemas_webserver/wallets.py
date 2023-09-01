from datetime import datetime
from decimal import Decimal
from typing import TypeAlias

from models_library.utils.pydantic_tools_extension import FieldNotRequired
from pydantic import Field, HttpUrl

from ..basic_types import IDStr
from ..users import GroupID
from ..utils.pydantic_tools_extension import FieldNotRequired
from ..wallets import WalletID, WalletStatus
from ._base import InputSchema, OutputSchema


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


#
# Payments to top-up credits in wallets
#

PaymentID: TypeAlias = IDStr  # identifier associated to a payment transaction


class CreateWalletPayment(InputSchema):
    price_dollars: Decimal
    osparc_credits: Decimal  # NOTE: should I recompute? or should be in the backend?
    comment: str = FieldNotRequired(max_length=100)


class WalletPaymentCreated(OutputSchema):
    payment_id: PaymentID
    payment_form_url: HttpUrl = Field(
        ..., description="Link to external site that holds the payment submission form"
    )


class PaymentTransaction(OutputSchema):
    payment_id: PaymentID
    price_dollars: Decimal
    wallet_id: WalletID
    osparc_credits: Decimal
    comment: str = FieldNotRequired()
    created_at: datetime
    completed_at: datetime | None
    invoice_url: HttpUrl = FieldNotRequired()
