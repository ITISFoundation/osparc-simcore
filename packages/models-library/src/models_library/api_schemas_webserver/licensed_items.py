from datetime import datetime
from typing import NamedTuple

from models_library.licensed_items import LicensedItemID, LicensedResourceType
from models_library.resource_tracker import PricingPlanId
from pydantic import ConfigDict, PositiveInt

from ._base import OutputSchema


class LicensedItemGet(OutputSchema):
    licensed_item_id: LicensedItemID
    name: str
    license_key: str | None
    licensed_resource_type: LicensedResourceType
    pricing_plan_id: PricingPlanId
    created_at: datetime
    modified_at: datetime
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "licensed_item_id": "0362b88b-91f8-4b41-867c-35544ad1f7a1",
                    "name": "best-model",
                    "license_key": "license-specific-key",
                    "licensed_resource_type": f"{LicensedResourceType.VIP_MODEL}",
                    "pricing_plan_id": "15",
                    "created_at": "2024-12-12 09:59:26.422140",
                    "modified_at": "2024-12-12 09:59:26.422140",
                }
            ]
        }
    )


class LicensedItemGetPage(NamedTuple):
    items: list[LicensedItemGet]
    total: PositiveInt
