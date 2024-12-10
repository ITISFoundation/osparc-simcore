from datetime import datetime
from decimal import Decimal
from typing import TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .licensed_items import LicensedItemID
from .products import ProductName
from .resource_tracker import PricingUnitCostId
from .users import UserID
from .wallets import WalletID

LicensedItemPurchaseID: TypeAlias = UUID


class LicensedItemsPurchasesCreate(BaseModel):
    product_name: ProductName
    licensed_item_id: LicensedItemID
    wallet_id: WalletID
    wallet_name: str
    pricing_unit_cost_id: PricingUnitCostId
    pricing_unit_cost: Decimal
    start_at: datetime
    expire_at: datetime
    num_of_seats: int
    purchased_by_user: UserID
    purchased_at: datetime

    model_config = ConfigDict(from_attributes=True)
