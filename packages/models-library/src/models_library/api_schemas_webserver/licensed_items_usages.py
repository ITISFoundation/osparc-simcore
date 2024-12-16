from datetime import datetime
from typing import NamedTuple

from pydantic import BaseModel, PositiveInt

from ..api_schemas_resource_usage_tracker.licensed_items_usages import LicenseCheckoutID
from ..licensed_items import LicensedItemID
from ..products import ProductName
from ..resource_tracker_licensed_items_usages import LicensedItemUsageID
from ..users import UserID
from ..wallets import WalletID
from ._base import OutputSchema


class LicensedItemUsageGet(OutputSchema):
    licensed_item_usage_id: LicensedItemUsageID
    licensed_item_id: LicensedItemID
    wallet_id: WalletID
    user_id: UserID
    product_name: ProductName
    started_at: datetime
    stopped_at: datetime | None
    num_of_seats: int


class LicensedItemUsageGetPage(NamedTuple):
    items: list[LicensedItemUsageGet]
    total: PositiveInt


class LicenseCheckoutGet(BaseModel):
    checkout_id: LicenseCheckoutID
