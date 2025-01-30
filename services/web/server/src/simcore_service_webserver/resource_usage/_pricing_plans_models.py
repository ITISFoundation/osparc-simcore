from models_library.resource_tracker import PricingPlanId
from models_library.rest_base import StrictRequestParameters


class PricingPlanGetPathParams(StrictRequestParameters):
    pricing_plan_id: PricingPlanId
