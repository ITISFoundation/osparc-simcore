from datetime import datetime

from ..api_schemas_webserver._base import OutputSchema
from ..api_schemas_webserver.resource_usage import PricingUnitGet
from ..resource_tracker import PricingPlanClassification, PricingPlanId


class ServicePricingPlanGet(OutputSchema):
    pricing_plan_id: PricingPlanId
    display_name: str
    description: str
    classification: PricingPlanClassification
    created_at: datetime
    pricing_plan_key: str
    pricing_units: list[PricingUnitGet]
