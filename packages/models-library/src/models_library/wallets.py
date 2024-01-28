from datetime import datetime
from decimal import Decimal
from enum import auto
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from .utils.enums import StrAutoEnum

WalletID: TypeAlias = PositiveInt


class WalletStatus(StrAutoEnum):
    ACTIVE = auto()
    INACTIVE = auto()


class WalletInfo(BaseModel):
    wallet_id: WalletID
    wallet_name: str
    model_config = ConfigDict()


ZERO_CREDITS = Decimal(0)

#
# DB
#


class WalletDB(BaseModel):
    wallet_id: WalletID
    name: str
    description: str | None = None
    owner: PositiveInt = Field(
        ...,
        description="GID of the group that owns this wallet",
    )
    thumbnail: str | None = None
    status: WalletStatus = Field(
        ...,
        description="Wallet status (ACTIVE or INACTIVE)",
    )
    created: datetime = Field(
        ...,
        description="Timestamp on creation",
    )
    modified: datetime = Field(
        ...,
        description="Timestamp of last modification",
    )


class UserWalletDB(WalletDB):
    read: bool
    write: bool
    delete: bool
