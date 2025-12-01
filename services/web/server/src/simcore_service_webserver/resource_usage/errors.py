from ..errors import WebServerBaseError


class ResourceUsageValueError(WebServerBaseError, ValueError): ...


class DefaultPricingPlanNotFoundError(ResourceUsageValueError):
    msg_template = "Default pricing plan not found"
