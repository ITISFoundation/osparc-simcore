from common_library.errors_classes import OsparcErrorMixin


class BaseDynamicSchedulerError(OsparcErrorMixin, ValueError):
    code = "simcore.service.dynamic.scheduler"  # type:ignore[assignment]
