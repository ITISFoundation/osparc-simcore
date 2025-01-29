from datetime import datetime
from typing import NamedTuple

from models_library.licensed_items import (
    LicensedItemID,
    LicensedResourceType,
    VipDetails,
)
from models_library.resource_tracker import PricingPlanId
from pydantic import BaseModel, ConfigDict, PositiveInt
from pydantic.alias_generators import to_camel

from ._base import OutputSchema

# RPC


class LicensedItemRpcGet(BaseModel):
    licensed_item_id: LicensedItemID
    display_name: str
    licensed_resource_type: LicensedResourceType
    pricing_plan_id: PricingPlanId
    licensed_resource_type_details: VipDetails
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
                    "licensed_resource_type_details": VipDetails.model_config[
                        "json_schema_extra"
                    ]["examples"][0],
                    "created_at": "2024-12-12 09:59:26.422140",
                    "modified_at": "2024-12-12 09:59:26.422140",
                }
            ]
        }
    )


class LicensedItemRpcGetPage(NamedTuple):
    items: list[LicensedItemRpcGet]
    total: PositiveInt


# Rest
class CustomBaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="allow"
    )

    def model_dump_camel(self):
        data = self.model_dump(by_alias=True)
        if hasattr(self, "__pydantic_extra__") and self.__pydantic_extra__:
            extra_camel = {to_camel(k): v for k, v in self.__pydantic_extra__.items()}
            data.update(extra_camel)
        return data


class LicensedItemRestGet(OutputSchema):
    licensed_item_id: LicensedItemID
    display_name: str
    licensed_resource_type: LicensedResourceType
    pricing_plan_id: PricingPlanId
    licensed_resource_type_details: VipDetails
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
                    "licensed_resource_type_details": VipDetails.model_config[
                        "json_schema_extra"
                    ]["examples"][0],
                    "created_at": "2024-12-12 09:59:26.422140",
                    "modified_at": "2024-12-12 09:59:26.422140",
                }
            ]
        }
    )


class LicensedItemRestGetPage(NamedTuple):
    items: list[LicensedItemRestGet]
    total: PositiveInt
