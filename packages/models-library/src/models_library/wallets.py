from datetime import datetime
from enum import auto
from typing import TypeAlias

from pydantic import BaseModel, Field, PositiveFloat, PositiveInt

from .basic_types import IDStr
from .utils.enums import StrAutoEnum

WalletID: TypeAlias = PositiveInt


class WalletStatus(StrAutoEnum):
    ACTIVE = auto()
    INACTIVE = auto()


class PaymentTransactionState(StrAutoEnum):
    CREATED = auto()
    COMPLETED = auto()


class PaymentTransaction(BaseModel):
    idr: IDStr
    prize: PositiveFloat
    wallet_id: WalletID
    credit: PositiveFloat
    comment: str
    state: PaymentTransactionState
    created: datetime
    completed: datetime | None


### DB


class WalletDB(BaseModel):
    wallet_id: WalletID
    name: str
    description: str | None
    owner: PositiveInt = Field(
        ...,
        description="GID of the group that owns this wallet",
    )
    thumbnail: str | None
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
