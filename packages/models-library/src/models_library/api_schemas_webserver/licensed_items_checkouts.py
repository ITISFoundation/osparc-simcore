from datetime import datetime
from typing import NamedTuple

from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel, ConfigDict, PositiveInt

from ..licenses import LicensedItemID
from ..products import ProductName
from ..resource_tracker_licensed_items_checkouts import LicensedItemCheckoutID
from ..users import UserID
from ..wallets import WalletID
from ._base import OutputSchema

# RPC


class LicensedItemCheckoutRpcGet(BaseModel):
    licensed_item_checkout_id: LicensedItemCheckoutID
    licensed_item_id: LicensedItemID
    wallet_id: WalletID
    user_id: UserID
    product_name: ProductName
    started_at: datetime
    stopped_at: datetime | None
    num_of_seats: int
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "licensed_item_checkout_id": "633ef980-6f3e-4b1a-989a-bd77bf9a5d6b",
                    "licensed_item_id": "0362b88b-91f8-4b41-867c-35544ad1f7a1",
                    "wallet_id": 6,
                    "user_id": 27845,
                    "product_name": "osparc",
                    "started_at": "2024-12-12 09:59:26.422140",
                    "stopped_at": "2024-12-12 09:59:26.423540",
                    "num_of_seats": 78,
                }
            ]
        }
    )


class LicensedItemCheckoutRpcGetPage(NamedTuple):
    items: list[LicensedItemCheckoutRpcGet]
    total: PositiveInt


# Rest


class LicensedItemCheckoutRestGet(OutputSchema):
    licensed_item_checkout_id: LicensedItemCheckoutID
    licensed_item_id: LicensedItemID
    wallet_id: WalletID
    user_id: UserID
    user_email: LowerCaseEmailStr
    product_name: ProductName
    started_at: datetime
    stopped_at: datetime | None
    num_of_seats: int


class LicensedItemCheckoutRestGetPage(NamedTuple):
    items: list[LicensedItemCheckoutRestGet]
    total: PositiveInt
