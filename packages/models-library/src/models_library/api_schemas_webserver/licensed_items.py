from datetime import datetime
from typing import NamedTuple, Self

from common_library.dict_tools import remap_keys
from models_library.licensed_items import (
    LicensedItemDB,
    LicensedItemID,
    LicensedResourceType,
)
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

    @classmethod
    def from_domain_model(cls, licensed_item_db: LicensedItemDB) -> Self:
        return cls.model_validate(
            remap_keys(
                licensed_item_db.model_dump(
                    include={
                        "licensed_item_id",
                        "licensed_resource_name",
                        "licensed_resource_type" "license_key",
                        "pricing_plan_id",
                        "created",
                        "modified",
                    }
                ),
                {
                    "licensed_resource_name": "name",
                    "created": "created_at",
                    "modified": "modified_at",
                },
            )
        )


class LicensedItemGetPage(NamedTuple):
    items: list[LicensedItemGet]
    total: PositiveInt
