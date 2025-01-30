from datetime import datetime
from typing import NamedTuple

from common_library.dict_tools import remap_keys
from models_library.licensed_items import (
    VIP_DETAILS_EXAMPLE,
    LicensedItemDB,
    LicensedItemID,
    LicensedResourceType,
)
from models_library.resource_tracker import PricingPlanId
from models_library.utils.common_validators import to_camel_recursive
from pydantic import AfterValidator, BaseModel, ConfigDict, PositiveInt
from typing_extensions import Annotated

from ._base import OutputSchema

# RPC


class LicensedItemRpcGet(BaseModel):
    licensed_item_id: LicensedItemID
    display_name: str
    licensed_resource_type: LicensedResourceType
    pricing_plan_id: PricingPlanId
    licensed_resource_type_details: dict[str, Any]
    created_at: datetime
    modified_at: datetime
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "licensed_item_id": "0362b88b-91f8-4b41-867c-35544ad1f7a1",
                    "display_name": "best-model",
                    "licensed_resource_type": f"{LicensedResourceType.VIP_MODEL}",
                    "pricing_plan_id": "15",
                    "licensed_resource_type_details": VIP_DETAILS_EXAMPLE,
                    "created_at": "2024-12-12 09:59:26.422140",
                    "modified_at": "2024-12-12 09:59:26.422140",
                }
            ]
        },
    )


class LicensedItemRpcGetPage(NamedTuple):
    items: list[LicensedItemRpcGet]
    total: PositiveInt


# Rest


class LicensedItemRestGet(OutputSchema):
    licensed_item_id: LicensedItemID
    display_name: str
    licensed_resource_type: LicensedResourceType
    pricing_plan_id: PricingPlanId
    licensed_resource_type_details: Annotated[
        dict[str, Any], AfterValidator(to_camel_recursive)
    ]
    created_at: datetime
    modified_at: datetime
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "licensed_item_id": "0362b88b-91f8-4b41-867c-35544ad1f7a1",
                    "display_name": "best-model",
                    "licensed_resource_type": f"{LicensedResourceType.VIP_MODEL}",
                    "pricing_plan_id": "15",
                    "licensed_resource_type_details": VIP_DETAILS_EXAMPLE,
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
                        "license_key",
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


class LicensedItemRestGetPage(NamedTuple):
    items: list[LicensedItemRestGet]
    total: PositiveInt
