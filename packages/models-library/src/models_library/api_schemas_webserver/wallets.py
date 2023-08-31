from datetime import datetime
from decimal import Decimal

from models_library.utils.pydantic_tools_extension import FieldNotRequired

from ..api_schemas_payments import payments as payments_service
from ..users import GroupID
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


class WalletPaymentCreateBody(InputSchema):
    prize_dollars: Decimal
    osparc_credits: Decimal  # NOTE: should I recompute? or should be in the backend?
    comment: str = FieldNotRequired(max_length=100)


class WalletPaymentGet(payments_service.PaymentGet):
    class Config(OutputSchema.Config):
        ...


class WalletPaymentItemList(payments_service.PaymentItemList):
    class Config(OutputSchema.Config):
        ...
