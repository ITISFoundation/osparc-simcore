from datetime import datetime
from decimal import Decimal
from typing import NamedTuple

from models_library.licensed_items import LicensedItemID
from models_library.products import ProductName
from models_library.resource_tracker import PricingUnitCostId
from models_library.resource_tracker_licensed_items_purchases import (
    LicensedItemPurchaseID,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import PositiveInt

from ._base import OutputSchema


class LicensedItemPurchaseGet(OutputSchema):
    licensed_item_purchase_id: LicensedItemPurchaseID
    product_name: ProductName
    licensed_item_id: LicensedItemID
    wallet_id: WalletID
    pricing_unit_cost_id: PricingUnitCostId
    pricing_unit_cost: Decimal
    start_at: datetime
    expire_at: datetime
    num_of_seats: int
    purchased_by_user: UserID
    purchased_at: datetime
    modified: datetime


class LicensedItemPurchaseGetPage(NamedTuple):
    items: list[LicensedItemPurchaseGet]
    total: PositiveInt
