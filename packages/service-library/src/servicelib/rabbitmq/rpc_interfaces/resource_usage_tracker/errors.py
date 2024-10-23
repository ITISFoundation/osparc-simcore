from common_library.errors_classes import OsparcErrorMixin


class ResourceUsageTrackerRuntimeError(OsparcErrorMixin, RuntimeError):
    msg_template: str = "Resource-usage-tracker unexpected error"


class CustomResourceUsageTrackerError(ResourceUsageTrackerRuntimeError):
    msg_template: str = "Error: {msg}"
