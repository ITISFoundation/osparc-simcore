from models_library.resource_tracker import PricingPlanId
from models_library.rest_base import StrictRequestParameters
from pydantic import ConfigDict


class PricingPlanGetPathParams(StrictRequestParameters):
    pricing_plan_id: PricingPlanId
    model_config = ConfigDict(extra="forbid")
