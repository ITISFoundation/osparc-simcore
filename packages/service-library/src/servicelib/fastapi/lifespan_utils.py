from common_library.errors_classes import OsparcErrorMixin


class LifespanError(OsparcErrorMixin, RuntimeError): ...


class LifespanOnStartupError(LifespanError):
    msg_template = "Failed during startup of {module}"


class LifespanOnShutdownError(LifespanError):
    msg_template = "Failed during shutdown of {module}"
