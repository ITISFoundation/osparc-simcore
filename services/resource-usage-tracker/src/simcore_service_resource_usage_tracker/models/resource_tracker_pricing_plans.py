from datetime import datetime

from models_library.resource_tracker import PricingPlanClassification, PricingPlanId
from pydantic import BaseModel


class PricingPlanDB(BaseModel):
    pricing_plan_id: PricingPlanId
    name: str
    description: str
    classification: PricingPlanClassification
    is_active: bool
    created: datetime

    class Config:
        orm_mode = True
