from common_library.errors_classes import OsparcErrorMixin


class ApplicationRuntimeError(OsparcErrorMixin, RuntimeError):
    pass


class ApplicationStateError(ApplicationRuntimeError):
    msg_template: str = "Invalid app.state.{state}: {msg}"
