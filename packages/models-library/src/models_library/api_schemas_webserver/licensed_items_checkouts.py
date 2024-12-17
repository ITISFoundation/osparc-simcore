from datetime import datetime
from typing import NamedTuple

from pydantic import BaseModel, PositiveInt

from ..api_schemas_resource_usage_tracker.licensed_items_checkouts import (
    LicenseCheckoutID,
)
from ..licensed_items import LicensedItemID
from ..products import ProductName
from ..resource_tracker_licensed_items_checkouts import LicensedItemCheckoutID
from ..users import UserID
from ..wallets import WalletID
from ._base import OutputSchema


class LicensedItemCheckoutGet(OutputSchema):
    licensed_item_checkout_id: LicensedItemCheckoutID
    licensed_item_id: LicensedItemID
    wallet_id: WalletID
    user_id: UserID
    product_name: ProductName
    started_at: datetime
    stopped_at: datetime | None
    num_of_seats: int


class LicensedItemUsageGetPage(NamedTuple):
    items: list[LicensedItemCheckoutGet]
    total: PositiveInt


class LicenseCheckoutGet(BaseModel):
    checkout_id: LicenseCheckoutID
