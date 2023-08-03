from datetime import datetime

from pydantic import BaseModel

from ..users import GroupID
from ..wallets import WalletID, WalletStatus


class WalletGet(BaseModel):
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
