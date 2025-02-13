from datetime import datetime
from decimal import Decimal

from models_library.emails import LowerCaseEmailStr
from models_library.licenses import LicensedItemID, LicensedItemKey, LicensedItemVersion
from models_library.products import ProductName
from models_library.resource_tracker import PricingUnitCostId
from models_library.resource_tracker_licensed_items_purchases import (
    LicensedItemPurchaseID,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, ConfigDict


class LicensedItemsPurchasesDB(BaseModel):
    licensed_item_purchase_id: LicensedItemPurchaseID
    product_name: ProductName
    licensed_item_id: LicensedItemID
    key: LicensedItemKey
    version: LicensedItemVersion
    wallet_id: WalletID
    wallet_name: str
    pricing_unit_cost_id: PricingUnitCostId
    pricing_unit_cost: Decimal
    start_at: datetime
    expire_at: datetime
    num_of_seats: int
    purchased_by_user: UserID
    user_email: LowerCaseEmailStr
    purchased_at: datetime
    modified: datetime

    model_config = ConfigDict(from_attributes=True)


class CreateLicensedItemsPurchasesDB(BaseModel):
    product_name: ProductName
    licensed_item_id: LicensedItemID
    key: LicensedItemKey
    version: LicensedItemVersion
    wallet_id: WalletID
    wallet_name: str
    pricing_unit_cost_id: PricingUnitCostId
    pricing_unit_cost: Decimal
    start_at: datetime
    expire_at: datetime
    num_of_seats: int
    purchased_by_user: UserID
    user_email: LowerCaseEmailStr
    purchased_at: datetime

    model_config = ConfigDict(from_attributes=True)
