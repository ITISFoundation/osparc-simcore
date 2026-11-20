from ..errors import WebServerBaseError


class ResourceUsageValueError(WebServerBaseError, ValueError): ...


class DefaultPricingPlanNotFoundError(ResourceUsageValueError):
    msg_template = "Default pricing plan not found"


class ResourceUsageTrackerNotAvailableError(WebServerBaseError):
    msg_template = "Resource usage tracker service is not available"
