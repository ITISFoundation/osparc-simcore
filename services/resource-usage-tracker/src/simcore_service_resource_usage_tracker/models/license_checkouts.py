from datetime import datetime

from models_library.licenses import LicenseID
from models_library.products import ProductName
from models_library.resource_tracker_license_checkouts import LicenseCheckoutID
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, ConfigDict


class LicenseCheckoutDB(BaseModel):
    license_checkout_id: LicenseCheckoutID
    license_id: LicenseID
    wallet_id: WalletID
    user_id: UserID
    user_email: str
    product_name: ProductName
    service_run_id: ServiceRunID
    started_at: datetime
    stopped_at: datetime | None
    num_of_seats: int
    modified: datetime

    model_config = ConfigDict(from_attributes=True)


class CreateLicenseCheckoutDB(BaseModel):
    license_id: LicenseID
    wallet_id: WalletID
    user_id: UserID
    user_email: str
    product_name: ProductName
    service_run_id: ServiceRunID
    started_at: datetime
    num_of_seats: int

    model_config = ConfigDict(from_attributes=True)


class UpdateLicenseCheckoutDB(BaseModel):
    stopped_at: datetime

    model_config = ConfigDict(from_attributes=True)
