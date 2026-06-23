from common_library.errors_classes import OsparcErrorMixin


class ComputationalSidecarRuntimeError(OsparcErrorMixin, RuntimeError): ...


class ConfigurationError(ComputationalSidecarRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"


class HTTPDestinationEncryptionNotSupportedError(ComputationalSidecarRuntimeError):
    msg_template: str = "Encryption is not supported for {scheme} upload destinations"
