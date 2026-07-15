from datetime import datetime
from decimal import Decimal
from enum import auto
from typing import Annotated, Final, NewType

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, TypeAdapter

from .groups import GroupID
from .utils.enums import StrAutoEnum

type _WalletIDInt = PositiveInt

WalletID = NewType("WalletID", _WalletIDInt)
WalletIDAdapter: Final[TypeAdapter[WalletID]] = TypeAdapter(WalletID)


class WalletStatus(StrAutoEnum):
    ACTIVE = auto()
    INACTIVE = auto()


class WalletInfo(BaseModel):
    wallet_id: WalletID
    wallet_name: str
    wallet_credit_amount: Decimal

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "wallet_id": 1,
                    "wallet_name": "My Wallet",
                    "wallet_credit_amount": Decimal(10),  # type: ignore[dict-item]
                }
            ]
        }
    )


ZERO_CREDITS = Decimal(0)

#
# DB
#


class WalletDB(BaseModel):
    wallet_id: WalletID
    name: str
    description: str | None
    owner: Annotated[
        GroupID,
        Field(
            description="GID of the group that owns this wallet",
        ),
    ]
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
