from datetime import datetime

from models_library.resource_tracker import PricingPlanClassification, PricingPlanId
from models_library.services import ServiceKey, ServiceVersion
from pydantic import BaseModel, ConfigDict

## DB Models


class PricingPlansDB(BaseModel):
    pricing_plan_id: PricingPlanId
    display_name: str
    description: str
    classification: PricingPlanClassification
    is_active: bool
    created: datetime
    pricing_plan_key: str
    model_config = ConfigDict(from_attributes=True)


class PricingPlansWithServiceDefaultPlanDB(PricingPlansDB):
    service_default_plan: bool
    model_config = ConfigDict(from_attributes=True)


class PricingPlanToServiceDB(BaseModel):
    pricing_plan_id: PricingPlanId
    service_key: ServiceKey
    service_version: ServiceVersion
    created: datetime
    model_config = ConfigDict(from_attributes=True)
