from typing import TypeAlias
from uuid import UUID

from models_library.api_schemas_resource_usage_tracker.licensed_items_usages import (
    LicenseCheckoutID,
)
from models_library.products import ProductName
from pydantic import BaseModel, ConfigDict

LicensedItemUsageID: TypeAlias = UUID


class LicenseCheckoutCreate(BaseModel):
    checkout_id: LicenseCheckoutID
    product_name: ProductName

    model_config = ConfigDict(from_attributes=True)
