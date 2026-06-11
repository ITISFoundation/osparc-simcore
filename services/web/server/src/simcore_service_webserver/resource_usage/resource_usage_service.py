"""Resource Usage public facade per DESIGN.md §133-152."""

from ._client import is_resource_usage_tracking_service_responsive
from .errors import DefaultPricingPlanNotFoundError, ResourceUsageValueError
from .service import (
    add_credits_to_wallet,
    get_default_service_pricing_plan,
    get_pricing_plan,
    get_pricing_plan_unit,
    get_wallet_total_available_credits,
)

__all__: tuple[str, ...] = (
    # exceptions
    "DefaultPricingPlanNotFoundError",
    "ResourceUsageValueError",
    # functions
    "add_credits_to_wallet",
    "get_default_service_pricing_plan",
    "get_pricing_plan",
    "get_pricing_plan_unit",
    "get_wallet_total_available_credits",
    "is_resource_usage_tracking_service_responsive",
)  # nopycln: file
