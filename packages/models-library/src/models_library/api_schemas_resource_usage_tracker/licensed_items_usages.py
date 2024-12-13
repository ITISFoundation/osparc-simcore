from datetime import datetime
from typing import NamedTuple, TypeAlias
from uuid import UUID

from models_library.licensed_items import LicensedItemID
from models_library.products import ProductName
from models_library.resource_tracker import ServiceRunId
from models_library.resource_tracker_licensed_items_usages import LicensedItemUsageID
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, ConfigDict, PositiveInt

LicenseCheckoutID: TypeAlias = UUID


class LicensedItemUsageGet(BaseModel):
    licensed_item_usage_id: LicensedItemUsageID
    licensed_item_id: LicensedItemID
    wallet_id: WalletID
    user_id: UserID
    product_name: ProductName
    service_run_id: ServiceRunId
    started_at: datetime
    stopped_at: datetime | None
    num_of_seats: int

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "licensed_item_usage_id": "beb16d18-d57d-44aa-a638-9727fa4a72ef",
                    "licensed_item_id": "303942ef-6d31-4ba8-afbe-dbb1fce2a953",
                    "wallet_id": 1,
                    "user_id": 1,
                    "product_name": "osparc",
                    "service_run_id": "run_1",
                    "started_at": "2023-01-11 13:11:47.293595",
                    "stopped_at": "2023-01-11 13:11:47.293595",
                    "num_of_seats": 1,
                }
            ]
        }
    )


class LicensedItemsUsagesPage(NamedTuple):
    items: list[LicensedItemUsageGet]
    total: PositiveInt


class LicenseItemCheckoutGet(BaseModel):
    checkout_id: LicenseCheckoutID  # This is a licensed_item_usage_id generated in the `resource_tracker_licensed_items_usages` table
