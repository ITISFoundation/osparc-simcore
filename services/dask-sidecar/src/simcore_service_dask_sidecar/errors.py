from common_library.errors_classes import OsparcErrorMixin


class ComputationalSidecarRuntimeError(OsparcErrorMixin, RuntimeError): ...


class ConfigurationError(ComputationalSidecarRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"


class EncryptionNotConfiguredError(ConfigurationError):
    msg_template: str = "Application misconfiguration: {msg}"


class HTTPDestinationEncryptionNotSupportedError(ComputationalSidecarRuntimeError):
    msg_template: str = "Encryption is not supported for {scheme} upload destinations"


class FileTransferEncryptionError(ComputationalSidecarRuntimeError):
    # NOTE: sidecar-internal translation of the low-level crypto failure. It carries
    # enough context (operation/file_role/file_id/error_message) for the caller to build
    # a client-facing ServiceEncryptionError without importing the crypto primitives.
    msg_template: str = "Could not securely {operation} the {file_role} file {file_id}: {error_message}"

    operation: str
    file_role: str
    file_id: str
    error_message: str
