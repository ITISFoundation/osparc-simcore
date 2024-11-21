from common_library.errors_classes import OsparcErrorMixin


class BaseDynamicSchedulerError(OsparcErrorMixin, ValueError):
    ...
