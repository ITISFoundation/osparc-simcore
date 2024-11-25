from common_library.errors_classes import OsparcErrorMixin


class ServiceIntegrationError(OsparcErrorMixin, RuntimeError):
    pass


class ConfigNotFoundError(ServiceIntegrationError):
    msg_template = "could not find any osparc config under {basedir}"


class UndefinedOciImageSpecError(ServiceIntegrationError):
    ...


class InvalidLabelsError(OsparcErrorMixin, ValueError):
    template_msg = "Invalid build labels {build_labels}"
