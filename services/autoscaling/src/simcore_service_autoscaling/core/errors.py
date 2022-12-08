from models_library.utils.change_case import camel_to_snake
from pydantic.errors import PydanticErrorMixin


class AutoscalingRuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "Autoscaling unexpected error"

    @classmethod
    @property
    def code(cls) -> str:
        return f"autoscaling.{camel_to_snake(cls.__name__)}"  # <--- code created automatically


class ConfigurationError(AutoscalingRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"


class Ec2NotConnectedError(AutoscalingRuntimeError):
    msg_template: str = "Cannot connect with ec2 server"


class Ec2InstanceNotFoundError(AutoscalingRuntimeError):
    msg_template: str = "Needed instance was not found"


class Ec2TooManyInstancesError(AutoscalingRuntimeError):
    msg_template: str = (
        "The maximum amount of instances {num_instances} is already reached!"
    )
