from common_library.errors_classes import OsparcErrorMixin


class ComputationalSidecarRuntimeError(OsparcErrorMixin, RuntimeError): ...


class ConfigurationError(ComputationalSidecarRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"
