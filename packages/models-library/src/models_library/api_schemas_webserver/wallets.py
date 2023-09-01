from datetime import datetime

from ..users import GroupID
from ..wallets import WalletID, WalletStatus
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
