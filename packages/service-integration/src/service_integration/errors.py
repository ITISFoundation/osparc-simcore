from pydantic.errors import PydanticErrorMixin


class ServiceIntegrationError(PydanticErrorMixin, RuntimeError):
    pass


class ConfigNotFoundError(ServiceIntegrationError):
    msg_template = "could not find any osparc config under {basedir}"


class UndefinedOciImageSpec(ServiceIntegrationError):
    ...
