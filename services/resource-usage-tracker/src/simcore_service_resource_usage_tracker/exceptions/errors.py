from common_library.errors_classes import OsparcErrorMixin


class ResourceUsageTrackerBaseError(OsparcErrorMixin, Exception):
    msg_template = "Resource usage Tracker Service Error"


class ConfigurationError(ResourceUsageTrackerBaseError):
    ...


###  NotCreatedDBError


class NotCreatedDBError(ResourceUsageTrackerBaseError):
    msg_template = "Data was not inserted to the DB. Data: {data}"


class ServiceRunNotCreatedDBError(NotCreatedDBError):
    ...


class CreditTransactionNotCreatedDBError(NotCreatedDBError):
    ...


class PricingPlanNotCreatedDBError(NotCreatedDBError):
    ...


class PricingUnitNotCreatedDBError(NotCreatedDBError):
    ...


class PricingUnitCostNotCreatedDBError(NotCreatedDBError):
    ...


class PricingPlanToServiceNotCreatedDBError(NotCreatedDBError):
    ...


### DoesNotExistsDBError


class PricingPlanDoesNotExistsDBError(ResourceUsageTrackerBaseError):
    msg_template = "Pricing plan {pricing_plan_id} does not exists"


class PricingPlanAndPricingUnitCombinationDoesNotExistsDBError(
    ResourceUsageTrackerBaseError
):
    msg_template = "Pricing plan {pricing_plan_id} and pricing unit {pricing_unit_id} does not exists in product {product_name}"


class PricingUnitCostDoesNotExistsDBError(ResourceUsageTrackerBaseError):
    msg_template = "Pricing unit cost id {pricing_unit_cost_id} does not exists"


### NotFoundError


class RutNotFoundError(ResourceUsageTrackerBaseError):
    ...


class PricingPlanNotFoundForServiceError(RutNotFoundError):
    msg_template = (
        "Pricing plan not found for service key {service_key} version {service_version}"
    )
