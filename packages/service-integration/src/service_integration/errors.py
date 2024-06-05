from pydantic.errors import PydanticErrorMixin


class ServiceIntegrationError(PydanticErrorMixin, RuntimeError):
    pass


class ConfigNotFoundError(ServiceIntegrationError):
    msg_template = "could not find any osparc config under {basedir}"


class UndefinedOciImageSpecError(ServiceIntegrationError):
    ...


class InvalidLabelsError(PydanticErrorMixin, ValueError):
    template_msg = "Invalid build labels {build_labels}"
