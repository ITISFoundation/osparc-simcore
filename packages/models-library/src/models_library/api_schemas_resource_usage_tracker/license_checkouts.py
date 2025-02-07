from datetime import datetime
from typing import NamedTuple

from models_library.licenses import LicenseID
from models_library.products import ProductName
from models_library.resource_tracker_license_checkouts import LicenseCheckoutID
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, ConfigDict, PositiveInt


class LicenseCheckoutGet(BaseModel):
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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "license_checkout_id": "beb16d18-d57d-44aa-a638-9727fa4a72ef",
                    "license_id": "303942ef-6d31-4ba8-afbe-dbb1fce2a953",
                    "wallet_id": 1,
                    "user_id": 1,
                    "user_email": "test@test.com",
                    "product_name": "osparc",
                    "service_run_id": "run_1",
                    "started_at": "2023-01-11 13:11:47.293595",
                    "stopped_at": "2023-01-11 13:11:47.293595",
                    "num_of_seats": 1,
                }
            ]
        }
    )


class LicenseCheckoutsPage(NamedTuple):
    items: list[LicenseCheckoutGet]
    total: PositiveInt
