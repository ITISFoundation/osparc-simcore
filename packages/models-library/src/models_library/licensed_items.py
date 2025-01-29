from datetime import datetime
from enum import auto
from typing import TypeAlias
from uuid import UUID

from pydantic import AliasGenerator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from .products import ProductName
from .resource_tracker import PricingPlanId
from .utils.enums import StrAutoEnum

LicensedItemID: TypeAlias = UUID


class LicensedResourceType(StrAutoEnum):
    VIP_MODEL = auto()


class VipFeatures(BaseModel):
    name: str
    version: str
    sex: str
    age: str
    weight: str
    height: str
    data: str
    ethnicity: str
    functionality: str

    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            serialization_alias=to_camel,
        ),
        populate_by_name=True,
        extra="allow",
        json_schema_extra={
            "examples": [
                {
                    "name": "Duke",
                    "version": "V2.0",
                    "sex": "Male",
                    "age": "34 years",
                    "weight": "70.2 Kg",
                    "height": "1.77 m",
                    "data": "2015-03-01",
                    "ethnicity": "Caucasian",
                    "functionality": "Static",
                    "additional_field": "allowed",
                }
            ]
        },
    )


class VipDetails(BaseModel):
    id: int
    description: str
    thumbnail: str
    features: VipFeatures
    doi: str
    license_key: str | None
    license_version: str | None
    protection: str
    available_from_url: str

    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            serialization_alias=to_camel,
        ),
        populate_by_name=True,
        extra="allow",
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "description": "custom description",
                    "thumbnail": "custom description",
                    "features": VipFeatures.model_config["json_schema_extra"][
                        "examples"
                    ][0],
                    "doi": "custom value",
                    "license_key": "custom value",
                    "license_version": "custom value",
                    "protection": "custom value",
                    "available_from_url": "custom value",
                    "additional_field": "allowed",
                }
            ]
        },
    )


#
# DB
#


class LicensedItemDB(BaseModel):
    licensed_item_id: LicensedItemID
    display_name: str
    licensed_resource_type: LicensedResourceType
    pricing_plan_id: PricingPlanId
    product_name: ProductName
    licensed_resource_type_details: VipDetails
    created: datetime = Field(
        ...,
        description="Timestamp on creation",
    )
    modified: datetime = Field(
        ...,
        description="Timestamp of last modification",
    )
    # ----
    model_config = ConfigDict(from_attributes=True)


class LicensedItemUpdateDB(BaseModel):
    display_name: str | None = None
    pricing_plan_id: PricingPlanId | None = None
