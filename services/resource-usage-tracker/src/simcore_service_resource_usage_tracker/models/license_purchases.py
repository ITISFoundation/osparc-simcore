from datetime import datetime
from decimal import Decimal

from models_library.emails import LowerCaseEmailStr
from models_library.licenses import LicenseID
from models_library.products import ProductName
from models_library.resource_tracker import PricingUnitCostId
from models_library.resource_tracker_license_purchases import LicensePurchaseID
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, ConfigDict


class LicensesPurchasesDB(BaseModel):
    licensed_item_purchase_id: LicensePurchaseID
    product_name: ProductName
    license_id: LicenseID
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


class CreateLicensesPurchasesDB(BaseModel):
    product_name: ProductName
    license_id: LicenseID
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
