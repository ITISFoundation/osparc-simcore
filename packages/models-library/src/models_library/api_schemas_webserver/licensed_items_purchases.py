from datetime import datetime
from decimal import Decimal
from typing import NamedTuple

from models_library.emails import LowerCaseEmailStr
from pydantic import PositiveInt

from ..licensed_items import LicensedItemID
from ..products import ProductName
from ..resource_tracker import PricingUnitCostId
from ..resource_tracker_licensed_items_purchases import LicensedItemPurchaseID
from ..users import UserID
from ..wallets import WalletID
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
    user_email: LowerCaseEmailStr
    purchased_at: datetime
    modified_at: datetime


class LicensedItemPurchaseGetPage(NamedTuple):
    items: list[LicensedItemPurchaseGet]
    total: PositiveInt
