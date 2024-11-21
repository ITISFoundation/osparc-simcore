from common_library.errors_classes import OsparcErrorMixin


class ClustersKeeperRuntimeError(OsparcErrorMixin, RuntimeError):
    msg_template: str = "clusters-keeper unexpected error"


class ConfigurationError(ClustersKeeperRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"
