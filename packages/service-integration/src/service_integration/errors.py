from pydantic.errors import PydanticErrorMixin


class ServiceIntegrationError(PydanticErrorMixin, RuntimeError):
    pass


class ConfigNotFound(ServiceIntegrationError):
    msg_template = "could not find any osparc config under {basedir}"
