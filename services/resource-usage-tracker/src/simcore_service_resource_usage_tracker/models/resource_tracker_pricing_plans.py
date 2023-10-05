from datetime import datetime

from models_library.resource_tracker import PricingPlanClassification, PricingPlanId
from pydantic import BaseModel


class PricingPlansDB(BaseModel):
    pricing_plan_id: PricingPlanId
    display_name: str
    description: str
    classification: PricingPlanClassification
    is_active: bool
    created: datetime
    pricing_plan_key: str

    class Config:
        orm_mode = True


class PricingPlansWithServiceDefaultPlanDB(PricingPlansDB):
    service_default_plan: bool

    class Config:
        orm_mode = True
