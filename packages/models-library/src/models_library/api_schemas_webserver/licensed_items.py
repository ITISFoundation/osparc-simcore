from datetime import datetime
from typing import Any, NamedTuple

from models_library.licensed_items import (
    VIP_DETAILS_EXAMPLE,
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
    licensed_resource_name: str
    licensed_resource_type: LicensedResourceType
    licensed_resource_data: dict[str, Any]
    pricing_plan_id: PricingPlanId
    created_at: datetime
    modified_at: datetime
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "licensed_item_id": "0362b88b-91f8-4b41-867c-35544ad1f7a1",
                    "licensed_resource_name": "best-model",
                    "licensed_resource_type": f"{LicensedResourceType.VIP_MODEL}",
                    "licensed_resource_data": VIP_DETAILS_EXAMPLE,
                    "pricing_plan_id": "15",
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
    licensed_resource_name: str
    licensed_resource_type: LicensedResourceType
    licensed_resource_data: Annotated[
        dict[str, Any], AfterValidator(to_camel_recursive)
    ]
    pricing_plan_id: PricingPlanId

    created_at: datetime
    modified_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "licensed_item_id": "0362b88b-91f8-4b41-867c-35544ad1f7a1",
                    "licensed_resource_name": "best-model",
                    "licensed_resource_type": f"{LicensedResourceType.VIP_MODEL}",
                    "licensed_resource_data": VIP_DETAILS_EXAMPLE,
                    "pricing_plan_id": "15",
                    "created_at": "2024-12-12 09:59:26.422140",
                    "modified_at": "2024-12-12 09:59:26.422140",
                }
            ]
        }
    )


class LicensedItemRestGetPage(NamedTuple):
    items: list[LicensedItemRestGet]
    total: PositiveInt
